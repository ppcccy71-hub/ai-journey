#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比三种检索：向量 / BM25 / 混合（RRF）。指标：hit@1、hit@5、MRR。"""
import json
import time
from pathlib import Path

import hybrid_retrieval as h
import step9_vector as s9

Q = Path(__file__).resolve().parent / "eval" / "questions_fastapi.json"


def evaluate(name, items, get_hits):
    hit1 = hit5 = 0
    mrr = 0.0
    t0 = time.perf_counter()
    for it in items:
        files = [c["source"] for _, c in get_hits(it["question"])]
        rank = next((i for i, f in enumerate(files, 1) if f in it["expect"]), None)
        if rank == 1:
            hit1 += 1
        if rank and rank <= 5:
            hit5 += 1
        if rank:
            mrr += 1.0 / rank
    n = len(items)
    ms = (time.perf_counter() - t0) * 1000 / n
    print(f"{name:<18} hit@1 {hit1}/{n}  hit@5 {hit5}/{n}  MRR {mrr / n:.3f}  {ms:.0f}ms/题")
    return hit1, hit5, mrr / n


def main():
    items = json.loads(Q.read_text(encoding="utf-8"))
    model, chunks = s9.load_vectors()
    bm25 = h.build_index(chunks)
    print(f"知识库 {len(chunks)} 块，{len(items)} 题\n")

    evaluate("向量（翻译）", items, lambda q: s9.search_plus(q, chunks, model, 5, True))
    evaluate("BM25（翻译）", items,
             lambda q: [(s, chunks[i]) for s, i in bm25.scores(s9.translate(q))[:5]])
    evaluate("混合 RRF（翻译）", items,
             lambda q: h.hybrid_search(q, chunks, model, 5, True, bm25))


if __name__ == "__main__":
    main()
