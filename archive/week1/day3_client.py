#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用自己写的 API —— 两个对照实验，验证"服务端无状态"。

先启动服务：
    python -m uvicorn day3_server:app --port 8000

再运行本脚本：
    python day3_client.py

你会看到：
    A 无历史 → 模型不知道你叫什么
    B 有历史 → 模型知道（因为"记忆"是客户端送上去的）
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def post(path, payload):
    """发一个 JSON 请求，返回解析后的响应字典。

    注意两点：
    1. 本地服务也要绕过系统代理（和 day1_first_call.py 同一个坑）
    2. HTTPError 里带着服务端的错误详情，要读出来才能看到 422 的具体原因
    """
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"[HTTP {e.code}] {detail}")
        return None


def main():
    # 先做个健康检查，确认服务活着
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(BASE + "/health", timeout=10) as r:
            print("健康检查:", json.loads(r.read().decode()))
    except Exception as e:
        print(f"服务没启动？先运行：python -m uvicorn day3_server:app --port 8000\n错误: {e}")
        return 1

    print("\n--- A：不传 history ---")
    r1 = post("/chat", {"message": "我叫什么？"})
    print("回答:", r1.get("reply") if r1 else "请求失败")

    print("\n--- B：传 history ---")
    r2 = post("/chat", {
        "message": "我叫什么？",
        "history": [
            {"role": "user", "content": "我叫小明"},
            {"role": "assistant", "content": "你好，小明！"},
        ],
    })
    print("回答:", r2.get("reply") if r2 else "请求失败")

    print("\n结论：同一个服务、同一句话，唯一区别是请求里有没有 history。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
