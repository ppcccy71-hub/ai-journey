#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Day 3：把命令行聊天程序变成 HTTP 服务。

运行：
    uvicorn day3_server:app --reload --port 8000

然后打开：
    http://127.0.0.1:8000/        简易聊天页面（浏览器里直接聊）
    http://127.0.0.1:8000/docs    自动生成的接口文档（可以直接点"Try it out"）

今天的三个接口：
    GET  /health        健康检查
    POST /chat          一次性返回完整回答（JSON）
    POST /chat/stream   流式返回（SSE，浏览器里逐字出现）
"""
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from day1_first_call import load_dotenv, stream_real

load_dotenv()

BASE = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")
SYSTEM = "你是一位简洁的老师，回答不超过 80 字。"

app = FastAPI(title="AI Chat API", version="0.1.0")


# ---------------- 请求体模型 ----------------
# Pydantic 模型 = 自动校验 + 自动生成文档。
# 字段写错类型，FastAPI 会直接返回 422，不用自己写 if 判断。
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户这句话")
    history: list[dict] = Field(
        default_factory=list,
        description="之前的对话历史，格式 [{role, content}]。由客户端维护——服务端不记任何人",
    )
    max_tokens: int = Field(200,ge=1,le=2000,description="模型输出token上限")
    temperature: float = Field(0.7, ge=0, le=2, description="采样随机性")


# ---------------- 内部工具 ----------------
def build_messages(req: ChatRequest):
    """把 system + 客户端传来的历史 + 本次问题拼成 messages。"""
    return [{"role": "system", "content": SYSTEM}, *req.history,
            {"role": "user", "content": req.message}]


def iter_reply(messages, temperature,max_tokens):
    """逐个 token 产出回答文本。

    注意这是个生成器：调用它不会发请求，只有被迭代时才真正开始。
    这和 Day 2 的 stream_real 是同一个道理。
    """
    if not KEY:
        raise HTTPException(status_code=500, detail="服务端未配置 API Key")
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    for obj in stream_real(BASE, KEY, payload, False):
        for choice in obj.get("choices", []):
            piece = (choice.get("delta") or {}).get("content")
            if piece:
                yield piece


# ---------------- 接口 ----------------
@app.get("/health")
def health():
    """健康检查：部署后第一个要访问的接口。"""
    return {"status": "ok", "model": MODEL}
@app.get("/model")
def model():
    return {"model": MODEL}

@app.post("/chat")
def chat(req: ChatRequest):
    """非流式：把流式结果攒完，一次性返回 JSON。

    适合：程序调用、批处理。
    不适合：需要即时反馈的聊天界面（用户要等全部生成完）。
    """
    reply = "".join(iter_reply(build_messages(req), req.temperature,req.max_tokens))
    return {"reply": reply, "model": MODEL}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """流式：用 StreamingResponse 把生成器包成 HTTP 流。

    关键点：生成器每 yield 一次，就向浏览器推一帧。
    下面这段是 SSE 格式，和 day1_first_call.py 里解析的格式一模一样——
    现在你是"生产方"，不是"消费方"了。
    """
    def event_generator():
        for piece in iter_reply(build_messages(req), req.temperature,req.max_tokens):
            data = json.dumps({"content": piece}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
def index():
    """极简聊天页：浏览器打开就能用。"""
    return """
<!doctype html>
<html lang="zh"><head><meta charset="utf-8"><title>AI Chat</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}
 #out{white-space:pre-wrap;border:1px solid #ddd;border-radius:8px;padding:12px;min-height:140px;line-height:1.7}
 input{width:100%;padding:10px;margin-top:12px;box-sizing:border-box;font-size:15px}
 .hint{color:#888;font-size:13px;margin-top:8px}
</style></head>
<body>
<h2>AI Chat（Day 3）</h2>
<div id="out">等待提问…</div>
<input id="q" placeholder="输入问题，回车发送" autofocus>
<div class="hint">接口文档：<a href="/docs">/docs</a></div>
<script>
const out = document.getElementById('out'), q = document.getElementById('q');
q.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter' || !q.value.trim()) return;
  const msg = q.value.trim(); q.value = ''; out.textContent = '';
  const res = await fetch('/chat/stream', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: msg}),
  });
  if (!res.ok) { out.textContent = '请求失败：' + res.status; return; }
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = '';
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream: true});
    const lines = buf.split('\\n'); buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const data = line.slice(5).trim();
      if (data === '[DONE]') continue;
      try { out.textContent += JSON.parse(data).content; } catch (_) {}
    }
  }
});
</script></body></html>
"""
