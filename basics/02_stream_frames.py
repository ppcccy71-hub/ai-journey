#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念 02：流式输出（SSE）到底是什么样。

这个例子不解析内容，只做一件事：把服务端推过来的原始文本行打印出来。
你会亲眼看到 data: {...} 一帧一帧到达，最后是 [DONE]。

运行：python 02_stream_frames.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    key = os.environ["LLM_API_KEY"]
    model = os.environ.get("LLM_MODEL", "deepseek-flash")

    body = {
        "model": model,
        "messages": [{"role": "user", "content": "数三个数：1、2、3"}],
        "stream": True,          # ← 唯一的开关
        "max_tokens": 50,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=60) as resp:
        for n, raw in enumerate(resp, start=1):
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                print(f"{n:>2} | (空行，帧分隔符)")
                continue
            print(f"{n:>2} | {line[:110]}")
            if line.endswith("[DONE]"):
                break

    print("\n每一行 data: {...} 就是一帧；delta.content 是新增的字。")


if __name__ == "__main__":
    main()
