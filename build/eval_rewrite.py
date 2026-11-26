#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比：追问原文检索 vs 改写后检索（均为向量 + rerank）。"""
import json
import time
from pathlib import Path

import query_rewrite
import rerank
import step9_vector as s9

Q = Path(__file__).resolve().parent / "eval" / "questions_followup.json"


def run(name, items, get_query):
    hit1 = hit5 = 0
    mrr = 0.0
    t0 = time.perf_counter()
    rows = []
    for it in items:
        q = get_query(it)
        hits = rerank.rerank(q, s9.search_plus(q, CHUNKS, MODEL, 20, True), 5)
        files = [c["source"] for _, c in hits]
        rank = next((i for i, f in enumerate(files, 1) if f in it["expect"]), None)
        hit1 += rank == 1
        hit5 += bool(rank and rank <= 5)
        mrr += 1.0 / rank if rank else 0
        rows.append((it["id"], rank, files[0], q))
    n = len(items)
    print(f"\n{name}: hit@1 {hit1}/{n}  hit@5 {hit5}/{n}  MRR {mrr / n:.3f}  "
          f"{(time.perf_counter() - t0) * 1000 / n:.0f}ms/题")
    for r in rows:
        print(f"  {r[0]} rank={r[1]} top1={r[2][:40]:<40} q={r[3][:50]}")
    return hit1, hit5


if __name__ == "__main__":
    items = json.loads(Q.read_text(encoding="utf-8"))
    MODEL, CHUNKS = s9.load_vectors()
    run("追问原文", items, lambda it: it["question"])
    run("改写后", items, lambda it: query_rewrite.rewrite(it["history"], it["question"]))
