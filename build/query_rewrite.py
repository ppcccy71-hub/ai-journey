#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多轮查询改写：把「那第二步呢」这类追问改写成独立查询。"""
import llm

SYS = (
    "你是查询改写助手。结合对话历史，把用户的最新问题改写成一个独立、完整的检索查询。"
    "补全省略的主语和指代，不要回答问题，不要解释。"
    "知识库是英文文档，输出英文查询，不超过 20 个词。"
)


def rewrite(history, question, max_turns=4):
    messages = [{"role": "system", "content": SYS}]
    for h in history[-max_turns:]:
        messages.append({"role": h["role"], "content": h["content"][:200]})
    messages.append({"role": "user", "content": question})
    text, _ = llm.stream_chat(messages, temperature=0, max_tokens=60)
    return text.strip().strip('"').strip("'")
