#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step7：查询改写 + 多路召回。"""
import argparse
import time
import step2_chunks as s2
import llm
from step3_retrieve import build_chunks, bigrams, score

SYSTEM_ANSWER = ("你是知识库助手。只能依据给定资料回答，每句话后用 [编号] 标注依据。\n"
                 "资料里没有答案时，直接回答：资料中没有相关信息。不要编造。")

def build_expand_prompt():
    """把文档标题和摘要塞进提示词，让模型用资料里的术语改写。"""
    digest = "\n".join(f"- {name}: {text.replace(chr(10), ' ')[:90]}"
                       for name, text in s2.load_docs())
    return ("你是查询改写助手。资料库包含以下文档：\n" + digest +
            "\n\n把用户问题改写成 3 个问法，必须优先使用资料里出现的术语"
            "（例如切块、上下文、状态码、线程池）。每行一个，不要编号。")

def expand_query(question,n=3):
    """生成 n 个同义问法，返回 [原问题, ...]。"""
    messages = [
        {"role": "system", "content": build_expand_prompt()},
        {"role":"user","content":question},
    ]
    text,_ = llm.stream_chat(messages,temperature=0.5,max_tokens=160)
    alts = []
    for line in text.splitlines():
        line = line.strip().lstrip("0123456789.、)").strip()
        if line and line !=question:
            alts.append(line)
    return [question] + alts[:n]

def retrieve_multi(queries,chunks,top_k=3):
    """每个问法都检索，同一个块取最高分。"""
    best = {}
    for q in queries:
        q_bg = bigrams(q)
        for c in chunks:
            s = score(q_bg,c["text"])
            key = id(c)
            if key not in best or s >best[key][0]:
                best[key] = (s,c)
    return sorted(best.values(),key=lambda x:-x[0])[:top_k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--min-score", type=float, default=0.3)
    ap.add_argument("--show-queries",action="store_true")
    args = ap.parse_args()

    chunks = build_chunks(size=300)
    t0 = time.perf_counter()
    queries = expand_query(args.question)
    hits = retrieve_multi(queries,chunks,args.top_k)
    best = hits[0][0] if hits else 0.0

    if args.show_queries:
        print("改写后的问法：")
        for q in queries:
            print(" -",q)
        print()


    print(f"[检索] {len(chunks)} 块 × {len(queries)} 个问法 → 最高分 {best:.2f}")
    if best < args.min_score:
        print("[拒答] 资料里没有相关内容（未调用模型）")
        return

    context = "\n\n".join(f"[{i}] 来源：{c['source']}\n{c['text']}"
                          for i, (_, c) in enumerate(hits, 1))

    messages = [
        {"role": "system", "content": SYSTEM_ANSWER},
        {"role": "user", "content": f"资料：\n{context}\n\n问题：{args.question}\n\n请依据资料回答并标注 [编号]。"},
    ]
    print()
    text,usage = llm.stream_chat(messages,temperature=0.2,max_tokens=400,
                                 on_piece=lambda p:print(p,end="",flush=True))
    usage = usage or {}
    print("\n")
    for i,(s,c) in enumerate(hits,1):
        print(f"  [{i}] {c['source']}({s:2f})")
    print(f"耗时 {time.perf_counter() - t0:.2f}s | token "
          f"{usage.get('prompt_tokens')} → {usage.get('completion_tokens')} | "
          f"${llm.cost(usage):.6f}")


if __name__ == "__main__":
    main()