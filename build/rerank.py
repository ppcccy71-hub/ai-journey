#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 LLM 给候选片段打相关性分，修正混合检索的排序。

一次调用给所有候选打分（批量），控制成本和延迟。
"""
import json
import re

import llm

SYS = (
    "你是检索排序助手。给定一个问题和若干资料片段，判断每个片段与问题的相关性，"
    "打分 0-10：10=直接回答，5=部分相关，0=无关。"
    "只输出一个 JSON 数组，长度与片段数一致，例如 [8,3,0]，不要输出其他内容。"
)


def rerank(question, hits, top_k=5, max_chars=300):
    if len(hits) <= 1:
        return hits[:top_k]

    lines = []
    for i, (_, c) in enumerate(hits, start=1):
        text = c["text"][:max_chars].replace("\n", " ")
        lines.append(f"[{i}] {text}")

    prompt = f"问题：{question}\n\n片段：\n" + "\n".join(lines)
    text, _ = llm.stream_chat(
        [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        temperature=0, max_tokens=200,
    )

    try:
        scores = json.loads(re.search(r"\[[^\]]*\]", text).group(0))
        if len(scores) != len(hits):
            raise ValueError("长度不一致")
    except Exception:
        return hits[:top_k]        # 解析失败就保持原排序

    order = sorted(range(len(hits)), key=lambda i: (-float(scores[i]), i))
    return [hits[i] for i in order[:top_k]]
