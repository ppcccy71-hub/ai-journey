#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day 4：并发与异步实验场 + 会话存储。

启动：
    python -m uvicorn day4_server:app --port 8000

实验接口（三个，都故意耗时 2 秒）：
    GET /slow/def         普通 def + time.sleep     ← 线程池执行，能并发
    GET /slow/async-block async def + time.sleep    ← 阻塞事件循环，全服务排队
    GET /slow/async-ok    async def + asyncio.sleep ← 不阻塞，真并发

会话接口：
    POST /chat             带 session_id 对话，历史存服务端（内存 + 文件）
    GET  /session/{sid}    查看某个会话的历史
    GET  /sessions         列出所有会话
"""
import asyncio
import json
import os
import sys
import time
from http.client import HTTPException
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from day1_first_call import load_dotenv, stream_real

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

load_dotenv()

BASE = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")
SYSTEM = "你是一位简洁的老师，回答不超过 80 字。"

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Day 4 · 并发实验场", version="0.1.0")


# ============================================================
# 一、并发实验：三个接口，同样"耗时 2 秒"，行为完全不同
# ============================================================
@app.get("/slow/def")
def slow_def():
    """普通 def：FastAPI 会把它丢进线程池，不占用事件循环。

    3 个并发请求 → 3 个线程同时睡 → 总耗时约 2 秒。
    """
    time.sleep(2)
    return {"mode": "def + time.sleep", "ok": True}


@app.get("/slow/async-block")
async def slow_async_block():
    """async def 里用阻塞的 time.sleep：整个事件循环被占住。

    3 个并发请求 → 只能一个一个来 → 总耗时约 6 秒。
    这就是"一个慢请求卡死整个服务"的真身。
    """
    time.sleep(2)
    return {"mode": "async def + time.sleep（错误示范）", "ok": True}


@app.get("/slow/async-ok")
async def slow_async_ok():
    """async def 里用 await asyncio.sleep：让出控制权，别的请求可以插进来。

    3 个并发请求 → 三个计时器同时跑 → 总耗时约 2 秒。
    """
    await asyncio.sleep(2)
    return {"mode": "async def + asyncio.sleep", "ok": True}


# ============================================================
# 二、会话存储：把 history 从客户端搬到服务端
# ============================================================
def session_file(sid: str) -> Path:
    # 简单防穿越：只允许字母数字、下划线、短横线
    safe = "".join(c for c in sid if c.isalnum() or c in "-_")
    return SESSIONS_DIR / f"{safe}.json"


def load_session(sid: str) -> list:
    p = session_file(sid)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save_session(sid: str, history: list) -> None:
    session_file(sid).write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64, description="会话 ID")
    message: str = Field(..., min_length=1, description="用户这句话")
    max_tokens: int = Field(200, ge=1, le=2000)


@app.post("/chat")
def chat(req: ChatRequest):
    """对话接口：历史存在服务端，客户端只传 session_id。

    注意这里用的是 def（不是 async def）：
    因为内部调用是阻塞的 urllib，放线程池里才不会卡住事件循环。
    """
    history = load_session(req.session_id)

    messages = [{"role": "system", "content": SYSTEM}, *history,
                {"role": "user", "content": req.message}]
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": req.max_tokens,
        "thinking": {"type": "disabled"},
    }

    parts = []
    for obj in stream_real(BASE, KEY, payload, False):
        for choice in obj.get("choices", []):
            piece = (choice.get("delta") or {}).get("content")
            if piece:
                parts.append(piece)
    reply = "".join(parts)

    # 写回历史：内存里没有，直接落文件（重启也不丢）
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})
    save_session(req.session_id, history)

    return {"session_id": req.session_id, "reply": reply, "turns": len(history) // 2}


@app.get("/session/{sid}")
def get_session(sid: str):
    history = load_session(sid)
    return {"session_id": sid, "turns": len(history) // 2, "history": history}

@app.delete("/session/{sid}")
def delete_session(sid: str):
    p = session_file(sid)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    p.unlink()
    return {"session_id": sid,"deleted": True}


@app.get("/sessions")
def list_sessions():
    items=[]
    for p in sorted(SESSIONS_DIR.glob("*.json")):
        history = load_session(p.stem)
        items.append({"session_id": p.stem, "turns": len(history) // 2, "updated_at":p.stat().st_mtime})
        return {"count":len(items), "sessions": items}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


# 直接运行本文件也能启动：python day4_server.py
# （等价于 python -m uvicorn day4_server:app --port 8000）
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("day4_server:app", host="127.0.0.1", port=8000)
