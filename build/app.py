import json
import threading
import uuid
from collections import defaultdict, deque
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import llm
import step9_vector as s9
import step8_embed as s8
import step13_agent as agent
import store
import agent_runs
import kb_index
import kb_store
import query_rewrite
import rerank
import os

SYSTEM = ("你是知识库助手。只能依据给定资料回答，每句话后用 [编号] 标注依据。\n"
          "资料里没有答案时，直接回答：资料中没有相关信息。不要编造。")

app = FastAPI(title="个人工作助手", version="0.2.0")

METRICS = {"total": 0, "errors": 0, "latency": 0.0, "paths": defaultdict(int)}
START_TS = time.time()


@app.middleware("http")
async def trace_and_metrics(request: Request, call_next):
    """给每个请求分配 trace_id，并记录基础指标。"""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    METRICS["total"] += 1
    METRICS["latency"] += elapsed
    METRICS["paths"][request.url.path] += 1
    if response.status_code >= 500:
        METRICS["errors"] += 1
    response.headers["X-Request-Id"] = rid
    return response



@app.middleware("http")
async def strip_api_prefix(request, call_next):
    """前端统一用 /api/xxx 调用；开发时 Vite 代理过来，生产时由这里剥掉前缀。"""
    if request.url.path.startswith("/api/"):
        request.scope["path"] = request.url.path[4:]
    return await call_next(request)


MODEL_V, CHUNKS = s9.load_vectors()
kb_store.init()
kb_index.ensure_default()

ENABLE_RERANK = os.environ.get("ENABLE_RERANK", "1") == "1"      # 检索后重排
ENABLE_REWRITE = os.environ.get("ENABLE_REWRITE", "1") == "1"    # 多轮查询改写

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")               # 为空则不校验
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))
_HITS = defaultdict(deque)


def guard(request: Request):
    """口令 + 每 IP 每分钟限流。公开部署时防止 key 被刷。"""
    if ACCESS_TOKEN and request.headers.get("x-access-token") != ACCESS_TOKEN:
        raise HTTPException(401, "需要访问口令（X-Access-Token）")
    # 云平台走反向代理，优先取 X-Forwarded-For 的第一个地址，否则所有人共用一个桶
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    now = time.time()
    q = _HITS[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "请求过于频繁，请稍后再试")
    q.append(now)          # 启动时加载一次


# ============================================================
# 请求模型
# ============================================================
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = Field(None, max_length=64, description="会话 ID，传了就会存历史")
    top_k: int = Field(5, ge=1, le=8)
    min_score: float = Field(0.45, ge=0, le=1)
    mode: str = Field("quality", pattern="^(speed|quality)$", description="speed=向量 top5，quality=top20+rerank")
    kb: str = Field("all", max_length=40, description="知识库 ID，all=全部库")


class SessionCreate(BaseModel):
    title: str = Field("新会话", max_length=50)


class AgentStreamRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = Field(None, max_length=64, description="会话 ID，用于多轮记忆")


class AgentApproveRequest(BaseModel):
    run_id: str = Field(..., min_length=1, max_length=32)
    approved: bool


class AgentRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=300)
    max_steps: int = Field(6, ge=1, le=10)


# ============================================================
# 检索与提示词
# ============================================================
def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def search(req: AskRequest):
    """检索：多轮改写 → 向量召回 10 条 → rerank 取 top_k。

    拒答阈值用召回阶段的余弦最高分，不能被 rerank 的排序分替代。
    """
    history = history_of(req.session_id) if ENABLE_REWRITE else []
    query = query_rewrite.rewrite(history, req.question) if history else req.question

    if req.mode == "quality" and not ENABLE_RERANK:
        req_mode = "speed"
    else:
        req_mode = req.mode
    return kb_index.search(req.kb, query, req.top_k, req_mode, has_cjk(query))


def history_of(sid, limit=6):
    """取该会话最近几条消息，作为多轮上下文。"""
    if not sid:
        return []
    msgs = store.get_messages(sid, limit=200)[-limit:]
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


def messages_of(req: AskRequest, hits):
    ctx = "\n\n".join(f"[{i}] 来源：{c['source']}\n{c['text']}"
                      for i, (_, c) in enumerate(hits, 1))
    return ([{"role": "system", "content": SYSTEM}]
            + history_of(req.session_id)
            + [{"role": "user", "content": f"资料：\n{ctx}\n\n问题：{req.question}\n\n请依据资料回答并标注 [编号]。"}])


def sources_of(hits):
    return [{"index": i, "source": c["source"], "score": round(s, 3)}
            for i, (s, c) in enumerate(hits, 1)]


def sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


# ============================================================
# 会话
# ============================================================
@app.post("/sessions")
def create_session(req: SessionCreate):
    sid = store.new_session(req.title)
    return {"id": sid, "title": req.title}


@app.get("/sessions")
def sessions():
    return {"sessions": store.list_sessions()}


@app.get("/sessions/{sid}")
def session_detail(sid: str):
    msgs = store.get_messages(sid)
    if not msgs and not any(s["id"] == sid for s in store.list_sessions(limit=200)):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": sid, "messages": msgs}


@app.delete("/sessions/{sid}")
def remove_session(sid: str):
    if not store.delete_session(sid):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"deleted": True, "session_id": sid}


# ============================================================
# 问答
# ============================================================
@app.get("/health")
def health():
    return {"status": "ok", "model": llm.MODEL, "chunks": len(CHUNKS),
            "llm_configured": bool(llm.BASE and llm.KEY),
            "embed_configured": bool(s8.BASE and s8.KEY),
            "access_protected": bool(ACCESS_TOKEN),
            "kbs": len(kb_store.list_kbs())}


@app.post("/ask")
def ask(req: AskRequest, request: Request):
    guard(request)
    t0 = time.perf_counter()
    hits, best = search(req)

    if best < req.min_score:
        answer, usage = "资料中没有相关信息。", {}
    else:
        answer, usage = llm.stream_chat(messages_of(req, hits), temperature=0.2, max_tokens=400)

    latency = int((time.perf_counter() - t0) * 1000)
    if req.session_id:
        store.ensure_session(req.session_id)
        store.add_message(req.session_id, "user", req.question)
        store.add_message(req.session_id, "assistant", answer)
        store.log_usage(req.session_id, "ask",
                        (usage or {}).get("prompt_tokens", 0),
                        (usage or {}).get("completion_tokens", 0),
                        llm.cost(usage), latency)

    return {"answer": answer, "refused": best < req.min_score, "best": round(best, 3),
            "sources": [] if best < req.min_score else sources_of(hits),
            "usage": usage or {}, "cost": round(llm.cost(usage), 8), "latency_ms": latency}


@app.post("/ask/stream")
def ask_stream(req: AskRequest, request: Request):
    guard(request)
    hits, best = search(req)

    def gen():
        if best < req.min_score:
            yield sse({"type": "sources", "sources": []})
            yield sse({"type": "refused", "text": "资料中没有相关信息。"})
            if req.session_id:
                store.ensure_session(req.session_id)
                store.add_message(req.session_id, "user", req.question)
                store.add_message(req.session_id, "assistant", "资料中没有相关信息。")
            yield "data: [DONE]\n\n"
            return

        yield sse({"type": "sources", "sources": sources_of(hits)})
        holder, parts = {}, []
        t0 = time.perf_counter()
        for piece in llm.iter_chat(messages_of(req, hits), temperature=0.2,
                                   max_tokens=400, usage_holder=holder):
            parts.append(piece)
            yield sse({"type": "delta", "text": piece})

        usage = holder.get("usage") or {}
        latency = int((time.perf_counter() - t0) * 1000)
        if req.session_id:
            store.ensure_session(req.session_id)
            store.add_message(req.session_id, "user", req.question)
            store.add_message(req.session_id, "assistant", "".join(parts))
            store.log_usage(req.session_id, "ask",
                            usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                            llm.cost(usage), latency)

        yield sse({"type": "done", "usage": usage, "cost": round(llm.cost(usage), 8),
                   "latency_ms": latency})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ============================================================
# Agent
# ============================================================
@app.post("/agent/run")
def agent_run(req: AgentRequest, request: Request):
    guard(request)
    t0 = time.perf_counter()
    trace = []
    try:
        answer = agent.run(req.task, req.max_steps, trace=trace)
    except Exception as e:
        answer = f"[异常] {type(e).__name__}: {e}"
    latency = int((time.perf_counter() - t0) * 1000)
    store.log_usage(None, "agent", 0, 0, 0.0, latency)
    files = sorted(p.name for p in agent.WORKSPACE.iterdir() if p.is_file())
    return {"answer": answer, "trace": trace, "files": files, "latency_ms": latency}


# ============================================================
# 统计
# ============================================================
@app.post("/agent/stream")
def agent_stream(req: AgentStreamRequest, request: Request):
    guard(request)
    """SSE：实时推送工具调用轨迹，写文件前等待人工确认。"""
    run = agent_runs.start(req.task, req.session_id)

    def gen():
        while True:
            evt = run.next_event(timeout=1.0)
            if evt is None:
                if run.done:
                    break
                yield ": ping\n\n"
                continue
            yield sse(evt)
            if evt["type"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/agent/approve")
def agent_approve(req: AgentApproveRequest, request: Request):
    guard(request)
    if not agent_runs.approve(req.run_id, req.approved):
        raise HTTPException(404, "任务不存在或已结束")
    return {"ok": True}


class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)


@app.get("/kbs")
def list_kbs(request: Request):
    guard(request)
    return {"items": kb_store.list_kbs()}


@app.post("/kbs")
def create_kb_endpoint(req: KBCreate, request: Request):
    guard(request)
    return kb_store.create_kb(req.name.strip())


@app.get("/kbs/{kb_id}")
def kb_detail(kb_id: str, request: Request):
    guard(request)
    kb = kb_store.get_kb(kb_id)
    if kb is None:
        raise HTTPException(404, "知识库不存在")
    kb["docs"] = kb_store.list_docs(kb_id)
    return kb


class KBRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)


@app.patch("/kbs/{kb_id}")
def rename_kb(kb_id: str, req: KBRename, request: Request):
    guard(request)
    if kb_store.get_kb(kb_id) is None:
        raise HTTPException(404, "知识库不存在")
    if kb_id == "fastapi":
        raise HTTPException(400, "内置知识库不能改名")
    kb_store.update_kb(kb_id, name=req.name.strip())
    return kb_store.get_kb(kb_id)


@app.delete("/kbs/{kb_id}")
def remove_kb(kb_id: str, request: Request):
    guard(request)
    if kb_store.get_kb(kb_id) is None:
        raise HTTPException(404, "知识库不存在")
    kb_index.path_of(kb_id).unlink(missing_ok=True)
    kb_store.delete_kb(kb_id)
    return {"ok": True}


@app.post("/kbs/{kb_id}/documents")
def upload_document(kb_id: str, request: Request, file: UploadFile = File(...)):
    guard(request)
    if kb_store.get_kb(kb_id) is None:
        raise HTTPException(404, "知识库不存在")
    if kb_id == "fastapi":
        raise HTTPException(400, "内置知识库只读，请新建知识库后再上传")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".md", ".txt", ".pdf"):
        raise HTTPException(400, "只支持 .md / .txt / .pdf")
    tmp = kb_index.KB_DIR / f"upload_{uuid.uuid4().hex}{suffix}"
    tmp.write_bytes(file.file.read())
    threading.Thread(target=kb_index.ingest_file, args=(kb_id, tmp, file.filename), daemon=True).start()
    return {"status": "indexing", "filename": file.filename}


@app.get("/metrics")
def metrics():
    """Prometheus 文本格式，方便接监控。"""
    stats = store.stats()
    total = max(1, METRICS["total"])
    lines = [
        "# HELP app_requests_total 总请求数",
        "# TYPE app_requests_total counter",
        f"app_requests_total {METRICS['total']}",
        "# HELP app_errors_total 5xx 数量",
        "# TYPE app_errors_total counter",
        f"app_errors_total {METRICS['errors']}",
        "# HELP app_avg_latency_seconds 平均请求耗时",
        "# TYPE app_avg_latency_seconds gauge",
        f"app_avg_latency_seconds {METRICS['latency'] / total:.4f}",
        "# HELP app_uptime_seconds 运行时长",
        "# TYPE app_uptime_seconds gauge",
        f"app_uptime_seconds {time.time() - START_TS:.0f}",
        "# HELP app_queries_total 问答次数",
        "# TYPE app_queries_total counter",
        f"app_queries_total {stats['queries']}",
        "# HELP app_tokens_total token 总量",
        "# TYPE app_tokens_total counter",
        f"app_tokens_total {stats['tokens_in'] + stats['tokens_out']}",
        "# HELP app_cost_usd 累计成本",
        "# TYPE app_cost_usd gauge",
        f"app_cost_usd {stats['total_cost']:.6f}",
        "# HELP app_kbs 知识库数量",
        "# TYPE app_kbs gauge",
        f"app_kbs {len(kb_store.list_kbs())}",
    ]
    for path, count in sorted(METRICS["paths"].items()):
        lines.append(f'app_requests_by_path{{path="{path}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n")


@app.get("/stats")
def stats():
    return store.stats()


@app.get("/stats/daily")
def stats_daily(days: int = 7):
    return {"days": days, "items": store.daily_stats(days)}


# 生产模式：托管前端构建产物（frontend/dist）。
# 必须在所有 API 路由之后挂载，否则会抢走 /api 的匹配。
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000)
