#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公共层：读配置 + 流式调模型。"""
import json
import os
import urllib.request
from pathlib import Path


ENV = Path(__file__).resolve().parent.parent / ".env"

def load_env():
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v = line.split("=", 1)
            os.environ.setdefault(k.strip(),v.strip())


load_env()
BASE = os.environ.get("LLM_BASE_URL","").rstrip("/")
KEY = os.environ.get("LLM_API_KEY","")
MODEL = os.environ.get("LLM_MODEL","deepseek-flash")
P_IN =float(os.environ.get("PRICE_IN","0")or 0)
P_OUT =float(os.environ.get("PRICE_OUT","0")or 0)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def iter_chat(massages,temperature=0.2, max_tokens=500,usage_holder = None):
    """流式调用：逐段产出文本（网页逐字显示靠它）。"""
    body = {"model":MODEL,"messages":massages,"stream":True,
            "temperature":temperature,"max_tokens":max_tokens,
            "thinking":{"type":"disabled"}}
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {KEY}"},
        method="POST"
    )
    with _OPENER.open(req,timeout=120) as resp:
        for raw in resp:
            line = raw.decode("utf-8","replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if obj.get("usage") and usage_holder is not None:
                usage_holder["usage"] = obj["usage"]
            for ch in obj.get("choices",[]):
                piece = (ch.get("delta") or {}).get("content")
                if piece:
                    yield piece

def stream_chat(messages, temperature=0.2, max_tokens = 500,on_piece=None):
    """流式调用，返回 (完整文本, usage)。"""
    holder,parts = {},[]
    for piece in iter_chat(messages,temperature,max_tokens,holder):
        parts.append(piece)
        if on_piece:
            on_piece(piece)
    return "".join(parts),holder.get("usage")

def cost(usage):
    if not usage:
        return 0.0
    return usage.get("prompt_tokens",0) / 1e6 *P_IN + usage.get("completion_tokens",0) / 1e6 *P_OUT
