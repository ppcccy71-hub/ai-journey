#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""混合检索：BM25（关键词）+ 向量，用 RRF 融合。

知识库是英文，中文问题先由 step9 翻译成英文，两路都用同一组查询。
"""
import math
import re
from collections import Counter

import jieba

import step9_vector as s9

K1, B = 1.5, 0.75
RRF_K = 60


def tokenize(text: str):
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.extend(w for w in jieba.cut(seg) if w.strip())
    return tokens


class BM25:
    def __init__(self, texts):
        self.docs = [tokenize(t) for t in texts]
        self.tf = [Counter(d) for d in self.docs]
        self.length = [len(d) for d in self.docs]
        self.N = len(self.docs)
        self.avgdl = sum(self.length) / max(1, self.N)
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {w: math.log(1 + (self.N - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def scores(self, query: str):
        q = [w for w in tokenize(query) if w in self.idf]
        out = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if not f:
                    continue
                denom = f + K1 * (1 - B + B * self.length[i] / max(1e-9, self.avgdl))
                s += self.idf[w] * f * (K1 + 1) / denom
            if s > 0:
                out.append((s, i))
        out.sort(key=lambda x: -x[0])
        return out


def rrf(rank_lists, top_k=5):
    """rank_lists: [[chunk_index, ...], ...]，按名次累加 1/(k+rank)。"""
    fused = {}
    for lst in rank_lists:
        for rank, idx in enumerate(lst, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(fused.items(), key=lambda x: -x[1])[:top_k]


def build_index(chunks):
    return BM25([c["text"] for c in chunks])


def hybrid_search(question, chunks, model, top_k=5, use_translate=True, bm25=None):
    bm25 = bm25 or build_index(chunks)
    queries = s9.build_queries(question, use_translate)

    index_of = {id(c): i for i, c in enumerate(chunks)}
    vector_ranked = []
    for q in queries:
        for _, c in s9.search(q, chunks, model, 20):
            idx = index_of[id(c)]
            if idx not in vector_ranked:
                vector_ranked.append(idx)

    lexical = {}
    for q in queries:
        for score, idx in bm25.scores(q)[:20]:
            lexical[idx] = max(lexical.get(idx, 0.0), score)
    lexical_ranked = [i for i, _ in sorted(lexical.items(), key=lambda x: -x[1])]

    fused = rrf([vector_ranked, lexical_ranked], top_k)
    return [(score, chunks[idx]) for idx, score in fused]
