#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""概念 01：一次 API 调用 + 它是怎么计费的。

看三件事：
1. 请求体里有哪些字段（model / messages / temperature / max_tokens）
2. 响应里的 usage 是什么
3. 成本怎么从 token 算出来

运行：python 01_call_and_cost.py
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
    """读根目录的 .env（KEY=VALUE 格式）。"""
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
    price_in = float(os.environ.get("PRICE_IN", "0"))
    price_out = float(os.environ.get("PRICE_OUT", "0"))

    # ---- 1. 请求体：这就是"一次调用"的全部输入 ----
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位简洁的老师，回答不超过 30 字。"},
            {"role": "user", "content": "用一句话解释什么是 token。"},
        ],
        "temperature": 0.2,
        "max_tokens": 100,
        "thinking": {"type": "disabled"},
    }

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕开系统代理
    with opener.open(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # ---- 2. 响应结构：choices 是答案，usage 是账单 ----
    print("回答：", data["choices"][0]["message"]["content"])
    print("结束原因：", data["choices"][0]["finish_reason"])

    usage = data["usage"]
    print("\nusage：", usage)

    # ---- 3. 计费：输入和输出分开算，单位是"每百万 token 的美元价" ----
    cost = usage["prompt_tokens"] / 1e6 * price_in + usage["completion_tokens"] / 1e6 * price_out
    print(f"本次成本：约 {cost:.8f} 美元")
    print("\n记住：token 是计费单位；输入含 system+user，输出含回答。")


if __name__ == "__main__":
    main()
