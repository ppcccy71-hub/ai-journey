#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.1：把知识助手包成 HTTP 服务 + 网页。

启动：
    python app.py
    # 或 python -m uvicorn app:app --port 8000

然后：
    http://127.0.0.1:8000/        网页问答
    http://127.0.0.1:8000/docs    接口文档
    POST /ask                     一次性返回（JSON）
    POST /ask/stream              流式返回（SSE，网页逐字显示）
"""
import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import llm
import rag

ROOT = Path(__file__).resolve().parent

SYSTEM = (
    "你是知识库助手。只能依据给定的资料回答问题。\n"
    "每句话后面用 [编号] 标注依据来自哪一段资料。\n"
    "如果资料里没有答案，直接回答：资料中没有相关信息。不要编造。"
)

app = FastAPI(title="个人知识助手 v1", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="你的问题")
    top_k: int = Field(3, ge=1, le=8, description="检索几块资料")
    min_score: float = Field(0.3, ge=0, le=1, description="低于该匹配度直接拒答")


def search(req: AskRequest):
    """检索：返回 (命中块列表, 最高分)。"""
    chunks = rag.load_chunks()
    hits = rag.retrieve(req.question, chunks, req.top_k)
    best = hits[0][0] if hits else 0.0
    return hits, best


def build_messages(req: AskRequest, hits):
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": rag.build_prompt(req.question, hits)},
    ]


def sources_of(hits):
    return [
        {"index": i, "source": c["source"], "score": round(s, 3), "preview": c["text"][:100]}
        for i, (s, c) in enumerate(hits, 1)
    ]


def sse(obj) -> str:
    """把字典包成一帧 SSE。"""
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


@app.get("/health")
def health():
    return {"status": "ok", "model": llm.MODEL, "chunks": len(rag.load_chunks())}


@app.post("/ask")
def ask(req: AskRequest):
    """一次性返回完整回答，适合程序调用。"""
    t0 = time.perf_counter()
    hits, best = search(req)

    if best < req.min_score:
        return {"answer": "资料中没有相关信息。", "refused": True, "sources": [],
                "usage": {}, "cost": 0.0, "latency_ms": int((time.perf_counter() - t0) * 1000)}

    text, usage = llm.stream_chat(build_messages(req, hits), temperature=0.2, max_tokens=500)
    return {
        "answer": text,
        "refused": False,
        "sources": sources_of(hits),
        "usage": usage or {},
        "cost": round(llm.cost_of(usage), 8),
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """流式返回：先推 sources，再逐字推 delta，最后 done。"""
    hits, best = search(req)

    def gen():
        if best < req.min_score:
            yield sse({"type": "sources", "sources": []})
            yield sse({"type": "refused", "text": "资料中没有相关信息。"})
            yield "data: [DONE]\n\n"
            return

        yield sse({"type": "sources", "sources": sources_of(hits)})

        holder = {}
        t0 = time.perf_counter()
        for piece in llm.iter_chat(build_messages(req, hits), temperature=0.2,
                                   max_tokens=500, usage_holder=holder):
            yield sse({"type": "delta", "text": piece})

        usage = holder.get("usage") or {}
        yield sse({"type": "done", "usage": usage, "cost": round(llm.cost_of(usage), 8),
                   "latency_ms": int((time.perf_counter() - t0) * 1000)})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000)
