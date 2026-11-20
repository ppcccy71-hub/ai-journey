#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step4：检索 top3 → 拼提示词 → 模型带引用回答。"""
import argparse
import time


import llm
from step3_retrieve import build_chunks, bigrams, score

SYSTEM = ("你是知识库助手。只能依据给定资料回答，每句话后用 [编号] 标注依据。\n"
          "资料里没有答案时，直接回答：资料中没有相关信息。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--top-k",type=int,default=3)
    ap.add_argument("--min-score",type=float,default=0.3,help="低于该分数直接拒答")
    args = ap.parse_args()

    chunks = build_chunks(size=300)
    q_bg = bigrams(args.question)
    hits = sorted(((score(q_bg,c["text"]),c)for c in chunks),key=lambda x:-x[0])[:args.top_k]

    # 拼上下文：[1] 来源：xxx
    context = "\n\n".join(f"[{i}] 来源: {c['source']}\n{c['text']}"
                           for i,(_,c) in enumerate(hits,1))
    messages = [
        {"role":"system","content":SYSTEM},
        {"role":"user","content": f"资料: \n{context}\n\n问题: {args.question}\n\n请依据资料回答并标注[编号]。"},
    ]

    best = hits[0][0] if hits else 0.0
    print(f"[检索] {len(chunks)}块 -> 取{len(hits)}块,最高分 {best:.2f}\n")

    if best < args.min_score:
        print("[拒答] 资料里没有相关内容(未调用模型，0 token)")
        return

    t0 = time.perf_counter()
    text, usage = llm.stream_chat(messages, temperature=0.2, max_tokens=500,
                                  on_piece=lambda p: print(p,end="",flush=True))

    print("\n")
    for i,(s,c) in enumerate(hits,1):
        print(f"  [{i}] {c['source']}({s:.2f})")
    print(f"耗时 {time.perf_counter() - t0:.2f}s | token"
          f"{usage.get('prompt_tokens')} -> {usage.get('completion_tokens')} | "
          f"${llm.cost(usage):.6f}")


if __name__ == "__main__":
    main()