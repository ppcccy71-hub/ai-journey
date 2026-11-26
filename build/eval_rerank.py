#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比：向量 / 混合 / 混合+rerank / 向量+rerank。"""
import json
import time
from pathlib import Path

import hybrid_retrieval as h
import rerank
import step9_vector as s9

Q = Path(__file__).resolve().parent / "eval" / "questions_fastapi.json"


def evaluate(name, items, get_hits):
    hit1 = hit5 = 0
    mrr = 0.0
    t0 = time.perf_counter()
    for it in items:
        files = [c["source"] for _, c in get_hits(it["question"])]
        rank = next((i for i, f in enumerate(files, 1) if f in it["expect"]), None)
        hit1 += rank == 1
        hit5 += bool(rank and rank <= 5)
        mrr += 1.0 / rank if rank else 0
    n = len(items)
    print(f"{name:<22} hit@1 {hit1}/{n}  hit@5 {hit5}/{n}  MRR {mrr / n:.3f}  "
          f"{(time.perf_counter() - t0) * 1000 / n:.0f}ms/题")


def main():
    items = json.loads(Q.read_text(encoding="utf-8"))
    model, chunks = s9.load_vectors()
    bm25 = h.build_index(chunks)
    print(f"知识库 {len(chunks)} 块，{len(items)} 题\n")

    def vec20(q):
        return s9.search_plus(q, chunks, model, 20, True)

    def hyb20(q):
        return h.hybrid_search(q, chunks, model, 20, True, bm25)

    evaluate("向量 top5", items, lambda q: s9.search_plus(q, chunks, model, 5, True))
    evaluate("混合 RRF top5", items, lambda q: h.hybrid_search(q, chunks, model, 5, True, bm25))
    evaluate("向量 + rerank", items, lambda q: rerank.rerank(q, vec20(q), 5))
    evaluate("混合 + rerank", items, lambda q: rerank.rerank(q, hyb20(q), 5))


if __name__ == "__main__":
    main()
