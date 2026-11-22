#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检索评测：每题标注应命中的源文件，统计 recall@1 / recall@5。

用法：
    python eval_retrieval.py
    python eval_retrieval.py --top-k 5
"""
import argparse
import json
import time
from pathlib import Path

import step9_vector as s9

QUESTIONS = Path(__file__).resolve().parent / "eval" / "questions_fastapi.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--translate", action="store_true", help="先翻译成英文再检索")
    args = ap.parse_args()

    items = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    model, chunks = s9.load_vectors()
    print(f"知识库 {len(chunks)} 块，模型 {model}，共 {len(items)} 题\n")

    hit1 = hit5 = 0
    total_ms = 0
    misses = []

    for it in items:
        t0 = time.perf_counter()
        hits = s9.search_mixed(it["question"], chunks, model, args.top_k, 2, args.translate)
        ms = int((time.perf_counter() - t0) * 1000)
        total_ms += ms

        files = [c["source"] for _, c in hits]
        ok1 = files[0] in it["expect"]
        ok5 = any(f in it["expect"] for f in files)
        hit1 += ok1
        hit5 += ok5
        if not ok5:
            misses.append((it, files, hits[0][0]))

        mark = "✅" if ok1 else ("🟡" if ok5 else "❌")
        print(f"{it['id']} {mark}  {ms:>4}ms  {files[0][:52]}")
        if not ok5:
            print(f"     期望：{it['expect']}")
            print(f"     实际：{files}")

    n = len(items)
    print("-" * 72)
    print(f"recall@1 : {hit1}/{n} = {hit1 / n * 100:.0f}%")
    print(f"recall@5 : {hit5}/{n} = {hit5 / n * 100:.0f}%")
    print(f"平均检索耗时 : {total_ms / n:.0f}ms")

    if misses:
        print(f"\n未命中 {len(misses)} 题（可记入 badcases.md）：")
        for it, files, best in misses:
            print(f"  {it['id']} 最高分 {best:.3f}  期望 {it['expect'][0]}  实际 {files[0]}")


if __name__ == "__main__":
    main()
