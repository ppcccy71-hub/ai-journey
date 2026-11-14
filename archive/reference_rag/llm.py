#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目公共层：读配置 + 调用模型。

以后所有功能（命令行、接口、评测）都从这里调模型，不要各写一份。
"""
import json
import os
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    """读 .env 到环境变量（KEY=VALUE 格式，忽略注释）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env()

BASE = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")
PRICE_IN = float(os.environ.get("PRICE_IN", "0") or 0)
PRICE_OUT = float(os.environ.get("PRICE_OUT", "0") or 0)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕开系统代理


def cost_of(usage: dict) -> float:
    """按 .env 里的单价算钱（美元）。"""
    if not usage:
        return 0.0
    return (usage.get("prompt_tokens", 0) / 1e6 * PRICE_IN
            + usage.get("completion_tokens", 0) / 1e6 * PRICE_OUT)


def iter_chat(messages, temperature=0.2, max_tokens=500, usage_holder=None):
    """流式调用，逐段产出文本（网页靠它实现逐字显示）。

    usage_holder 是个字典，调用方传 {} 进来，结束后里面会有 usage。
    """
    if not KEY:
        raise RuntimeError("没有 API Key，请检查 .env")

    body = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST",
    )

    with _OPENER.open(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
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
            for choice in obj.get("choices", []):
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    yield piece


def stream_chat(messages, temperature=0.2, max_tokens=500, on_piece=None):
    """阻塞版流式：边回调边收集，最后返回 (完整文本, usage)。

    命令行用它（边打印），接口用 iter_chat（边推送）。
    """
    holder = {}
    parts = []
    for piece in iter_chat(messages, temperature, max_tokens, holder):
        parts.append(piece)
        if on_piece:
            on_piece(piece)
    return "".join(parts), holder.get("usage")
