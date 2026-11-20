#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step3：给一个问题，找出最相关的 3 块。

检索的本质就是"打分 + 排序"：
    问题 → 拆成二元组 → 和每个块比对 → 算出重合比例 → 取前 K 个
"""
import argparse
import re

import step2_chunks as s2 # 复用切块，不重复写

def bigrams(text:str):
    """去掉空白和标点，取相邻两个字，组成二元组列表。"""
    text = re.sub(r"[\s\W]+", " ", text.lower())
    return [text[i:i + 2] for i in range(len(text) - 1)]

def score(query_bg, chunk_text:str)->float:
    """问题里的二元组，有多大比例出现在块里。"""
    chunk_bg = set(bigrams(chunk_text))
    if not query_bg or not chunk_bg:
        return 0.0
    hit = sum(1 for bg in query_bg if bg in chunk_bg)
    return hit / len(query_bg)

def build_chunks(size=300):
    """把三篇文档都切成块，每块记住它来自哪篇。"""
    chunks = []
    for name,text in s2.load_docs():
        for c in s2.chunk_text(text,size=size):
            chunks.append({"text":c,"source":name})
    return chunks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--top-k", type=int, default=3)
    args = ap.parse_args()

    chunks = build_chunks(size=300)
    q_bg = bigrams(args.question)

    scored = sorted(((score(q_bg, c["text"]),c)for c in chunks), key=lambda x:-x[0])
    print(f"[检索] {len(chunks)}块,问题拆成{len(q_bg)}个二元组\n")
    for s,c in scored[:args.top_k]:
        print(f"  {s:.2f} {c['source']:<18} {c['text'][:50].replace(chr(10),' ')}...")

if __name__ == "__main__":
    main()
