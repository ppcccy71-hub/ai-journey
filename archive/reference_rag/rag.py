#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目检索层：切块 + 关键词检索 + 拼提示词。

三个函数就是 RAG 的前半段：
    load_chunks()  文档 → 块
    retrieve()     问题 → 最相关的几块
    build_prompt() 块 + 问题 → 给模型的提示词
"""
import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent / "docs"


def load_chunks(docs_dir: Path = DOCS_DIR, size: int = 320, overlap: int = 60):
    """按段落切块：够短就合并，太长就断开，相邻块留一点重叠。"""
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

        buf = ""
        for para in paras:
            if len(buf) + len(para) <= size:
                buf = f"{buf}\n{para}".strip()
                continue
            if buf:
                chunks.append({"text": buf, "source": path.name})
                buf = (buf[-overlap:] + "\n" + para).strip() if overlap else para
            else:
                buf = para
        if buf:
            chunks.append({"text": buf, "source": path.name})
    return chunks


def _bigrams(text: str):
    """中文不分词也能用：取相邻两个字组成二元组，比较重合度。"""
    text = re.sub(r"[\s\W_]+", "", text.lower())
    return [text[i:i + 2] for i in range(len(text) - 1)]


def retrieve(question: str, chunks, top_k: int = 3):
    """给每个块打分：命中的二元组比例。返回 [(分数, 块), ...]。"""
    q_bg = _bigrams(question)
    scored = []
    for c in chunks:
        c_bg = set(_bigrams(c["text"]))
        if not q_bg or not c_bg:
            scored.append((0.0, c))
            continue
        hit = sum(1 for bg in q_bg if bg in c_bg)
        scored.append((hit / len(q_bg), c))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]


def build_prompt(question: str, hits) -> str:
    """把检索结果编号后拼进提示词——编号就是引用的来源。"""
    parts = [f"[{i}] 来源：{c['source']}\n{c['text']}" for i, (_, c) in enumerate(hits, 1)]
    return ("资料：\n" + "\n\n".join(parts)
            + f"\n\n问题：{question}\n\n请依据资料回答，并标注 [编号]。")
