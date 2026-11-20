#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step9：用向量算相似度，替换关键词匹配。"""
import argparse
import json
import math
from pathlib import Path

import step8_embed as s8

ROOT = Path(__file__).resolve().parent
VEC_FILE = ROOT / "vectors.json"


def cosine(a,b):
    """余弦相似度：两个向量夹角的余弦，值域 -1~1，越接近 1 越像。"""
    dot = sum (x * y for x,y in zip(a,b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum (y * y for y in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def load_vectors():
    data = json.loads(VEC_FILE.read_text(encoding="utf-8"))
    return data["model"], data["chunks"]

def search(question,chunks,model,top_k=3):
    """把问题也变成向量，和每个块算余弦，取前 K。"""
    vecs,_=s8.embed([question],model)
    qv=vecs[0]
    scored = [(cosine(qv,c["vector"]),c) for c in chunks]
    return sorted(scored,key=lambda x:-x[0])[:top_k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--top_k", type=int, default=3)
    args = ap.parse_args()


    model,chunks = load_vectors()
    hits = search(args.question,chunks,model,args.top_k)

    print(f"[向量检索] {len(chunks)} 块，模型 {model}\n")
    for s,c in hits:
        print(f"  {s:.3f}  {c['source']:<18} {c['text'][:45].replace(chr(10), ' ')}…")



if __name__ == "__main__":
    main()