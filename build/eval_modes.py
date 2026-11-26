#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两种检索模式对比：speed（向量 top5） vs quality（向量 top20 + rerank）。"""
import json
import time
from pathlib import Path

import rerank
import step9_vector as s9

Q = Path(__file__).resolve().parent / "eval" / "questions_fastapi.json"


def run(name, items, fn):
    hit1 = hit5 = 0
    mrr = 0.0
    t0 = time.perf_counter()
    for it in items:
        hits = fn(it["question"])
        files = [c["source"] for _, c in hits]
        rank = next((i for i, f in enumerate(files, 1) if f in it["expect"]), None)
        hit1 += rank == 1
        hit5 += bool(rank and rank <= 5)
        mrr += 1.0 / rank if rank else 0
    n = len(items)
    print(f"{name:<26} hit@1 {hit1}/{n}  hit@5 {hit5}/{n}  MRR {mrr / n:.3f}  "
          f"{(time.perf_counter() - t0) * 1000 / n:.0f}ms/题")


def main():
    items = json.loads(Q.read_text(encoding="utf-8"))
    model, chunks = s9.load_vectors()
    print(f"知识库 {len(chunks)} 块，{len(items)} 题\n")

    run("speed：向量 top5", items,
        lambda q: s9.search_plus(q, chunks, model, 5, True))
    run("quality：top20 + rerank", items,
        lambda q: rerank.rerank(q, s9.search_plus(q, chunks, model, 20, True), 5))


if __name__ == "__main__":
    main()
