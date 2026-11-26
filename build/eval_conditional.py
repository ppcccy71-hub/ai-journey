#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""条件 rerank：余弦最高分低于阈值才重排，否则直接用召回结果。"""
import json
import time
from pathlib import Path

import rerank
import step9_vector as s9

Q = Path(__file__).resolve().parent / "eval" / "questions_fastapi.json"
THRESHOLD = 0.78


def main():
    items = json.loads(Q.read_text(encoding="utf-8"))
    model, chunks = s9.load_vectors()

    for threshold in (0.72, 0.78, 0.85):
        hit1 = hit5 = 0
        mrr = 0.0
        reranked = 0
        t0 = time.perf_counter()
        for it in items:
            cand = s9.search_plus(it["question"], chunks, model, 10, True)
            best = cand[0][0] if cand else 0.0
            if best < threshold:
                hits = rerank.rerank(it["question"], cand, 5)
                reranked += 1
            else:
                hits = cand[:5]
            files = [c["source"] for _, c in hits]
            rank = next((i for i, f in enumerate(files, 1) if f in it["expect"]), None)
            hit1 += rank == 1
            hit5 += bool(rank and rank <= 5)
            mrr += 1.0 / rank if rank else 0
        n = len(items)
        print(f"阈值 {threshold}: hit@1 {hit1}/{n}  hit@5 {hit5}/{n}  MRR {mrr / n:.3f}  "
              f"rerank {reranked}/{n}  {(time.perf_counter() - t0) * 1000 / n:.0f}ms/题")


if __name__ == "__main__":
    main()
