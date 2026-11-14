#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.0 命令行版：python cli.py "你的问题"

流程：切块 → 检索 → 拼提示词 → 调用模型 → 打印回答和出处。
"""
import argparse
import sys
import time

import llm
import rag

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SYSTEM = (
    "你是知识库助手。只能依据给定的资料回答问题。\n"
    "每句话后面用 [编号] 标注依据来自哪一段资料。\n"
    "如果资料里没有答案，直接回答：资料中没有相关信息。不要编造。"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", help="你的问题")
    ap.add_argument("--top-k", type=int, default=3, help="检索几块")
    ap.add_argument("--show-chunks", action="store_true", help="打印检索到的块和分数")
    ap.add_argument("--min-score", type=float, default=0.3, help="低于该分数直接拒答")
    args = ap.parse_args()

    chunks = rag.load_chunks()
    hits = rag.retrieve(args.question, chunks, args.top_k)
    best = hits[0][0] if hits else 0.0
    print(f"[检索] {len(chunks)} 块 → 取 {len(hits)} 块，最高匹配度 {best:.2f}")

    if best < args.min_score:
        print("[拒答] 知识库里找不到相关内容，不调用模型（省钱）")
        return

    if args.show_chunks:
        for i, (s, c) in enumerate(hits, 1):
            print(f"  [{i}] {s:.2f}  {c['source']}  {c['text'][:50]}...")

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": rag.build_prompt(args.question, hits)},
    ]

    t0 = time.perf_counter()
    text, usage = llm.stream_chat(
        messages, temperature=0.2, max_tokens=500,
        on_piece=lambda p: print(p, end="", flush=True),
    )
    print("\n")

    print("--- 出处 ---")
    for i, (s, c) in enumerate(hits, 1):
        print(f"  [{i}] {c['source']}（匹配度 {s:.2f}）")
    print(f"--- 耗时 {time.perf_counter() - t0:.2f}s | token "
          f"输入 {usage.get('prompt_tokens')} 输出 {usage.get('completion_tokens')} "
          f"| 成本 {llm.cost_of(usage):.6f} 美元 ---")


if __name__ == "__main__":
    main()
