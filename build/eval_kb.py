#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测指定知识库的检索效果。

题库格式：
[
  {"question": "内幕信息知情人包括哪些？", "expect": ["内幕信息知情人", "第X条"]},
  ...
]
命中判定：前 k 个块中，任意一块的文本包含 expect 里任一关键词。

用法：
    python eval_kb.py --kb 金融合规 --questions eval/finance_questions.json
"""
import argparse
import json
import time
from pathlib import Path

import kb_index

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    items = json.loads((ROOT / args.questions).read_text(encoding="utf-8"))
    data = kb_index.load(args.kb)
    if not data:
        raise SystemExit(f"知识库不存在：{args.kb}")
    print(f"知识库 {args.kb}：{len(data['chunks'])} 块，{len(items)} 题\n")

    hit1 = hit5 = 0
    mrr = 0.0
    t0 = time.perf_counter()
    misses = []
    for it in items:
        hits, _ = kb_index.search(args.kb, it["question"], args.top_k, "speed", True)
        rank = None
        for i, (_, c) in enumerate(hits, 1):
            if any(k.lower() in c["text"].lower() for k in it["expect"]):
                rank = i
                break
        hit1 += rank == 1
        hit5 += bool(rank and rank <= 5)
        mrr += 1.0 / rank if rank else 0
        mark = "✅" if rank == 1 else ("🟡" if rank else "❌")
        print(f"{mark} {it['question'][:40]:<42} rank={rank}")
        if not rank:
            misses.append(it["question"])

    n = len(items)
    print("-" * 60)
    print(f"hit@1 {hit1}/{n}  hit@5 {hit5}/{n}  MRR {mrr / n:.3f}  "
          f"{(time.perf_counter() - t0) * 1000 / n:.0f}ms/题")
    if misses:
        print("\n未命中：")
        for m in misses:
            print("  -", m)


if __name__ == "__main__":
    main()
