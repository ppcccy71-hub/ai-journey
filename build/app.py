import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import llm
import step9_vector as s9
import step13_agent as agent
import store

SYSTEM = ("你是知识库助手。只能依据给定资料回答，每句话后用 [编号] 标注依据。\n"
          "资料里没有答案时，直接回答：资料中没有相关信息。不要编造。")

app = FastAPI(title="个人工作助手", version="0.2.0")


@app.middleware("http")
async def strip_api_prefix(request, call_next):
    """前端统一用 /api/xxx 调用；开发时 Vite 代理过来，生产时由这里剥掉前缀。"""
    if request.url.path.startswith("/api/"):
        request.scope["path"] = request.url.path[4:]
    return await call_next(request)


MODEL_V, CHUNKS = s9.load_vectors()          # 启动时加载一次


# ============================================================
# 请求模型
# ============================================================
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = Field(None, max_length=64, description="会话 ID，传了就会存历史")
    top_k: int = Field(5, ge=1, le=8)
    min_score: float = Field(0.45, ge=0, le=1)


class SessionCreate(BaseModel):
    title: str = Field("新会话", max_length=50)


class AgentRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=300)
    max_steps: int = Field(6, ge=1, le=10)


# ============================================================
# 检索与提示词
# ============================================================
def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def search(req: AskRequest):
    # 知识库是英文文档：中文提问先翻成英文再检索，recall@5 从 95% 提到 100%
    hits = s9.search_mixed(req.question, CHUNKS, MODEL_V, req.top_k, 2, has_cjk(req.question))
    return hits, (hits[0][0] if hits else 0.0)


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
    return {"status": "ok", "model": llm.MODEL, "chunks": len(CHUNKS)}


@app.post("/ask")
def ask(req: AskRequest):
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
def ask_stream(req: AskRequest):
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
def agent_run(req: AgentRequest):
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
