#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金融合规知识库的端到端评测：调用本地 /api/ask。"""
import json
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8109"
KB = "金融合规"
Q = Path(__file__).resolve().parent / "eval" / "finance_questions.json"
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
REFUSAL = "资料中没有相关信息"


def ask(question):
    body = json.dumps({"question": question, "kb": KB, "mode": "speed"}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with OP.open(req, timeout=120) as r:
        return json.loads(r.read())


def main():
    items = json.loads(Q.read_text(encoding="utf-8"))
    ok = 0
    t0 = time.perf_counter()
    for it in items:
        data = ask(it["question"])
        answer = data.get("answer", "")
        refused = data.get("refused") or answer.startswith(REFUSAL) or REFUSAL in answer[:20]
        if it["type"] == "refuse":
            good = refused
        else:
            good = (not refused) and any(k.lower() in answer.lower() for k in it["expect"])
        ok += good
        src = data.get("sources", [{}])[0].get("source", "-")
        mark = "✅" if good else "❌"
        print(f"{mark} {it['id']} {it['question'][:34]:<36} {src[:36]}")
        if not good:
            print("   答:", answer[:90].replace("\n", " "))
    n = len(items)
    print("-" * 64)
    print(f"准确率 {ok}/{n} = {ok / n * 100:.0f}%   "
          f"{(time.perf_counter() - t0) * 1000 / n:.0f}ms/题")


if __name__ == "__main__":
    main()
