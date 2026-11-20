#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step6：跑 20 条评测集，算出准确率、拒答率、耗时、成本。"""
import step9_vector as s9
import argparse
import json
import time
from pathlib import Path

import llm
from step3_retrieve import build_chunks,bigrams,score

SYSTEM = ("你是知识库助手。只能依据给定资料回答，每句话后用 [编号] 标注依据。\n"
          "资料里没有答案时，直接回答：资料中没有相关信息。不要编造。")
QUESTIONS = Path(__file__).resolve().parent / "eval" / "questions.json"

def is_refusal(text):
    return any(k in text for k in ["没有相关信息", "没有找到", "资料中没有", "无法回答", "不知道"])

def judge(item, text):
    """answer 题：出现任一关键词算对；refuse 题：拒答话术或被阈值拒答都算对。"""
    if item["type"] == "refuse":
        return text.startswith("[拒答]") or  is_refusal(text)
    return any(k.lower() in text.lower() for k in item.get("expect",[]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file",default="questions.json",help="eval 目录下的题库文件名")
    ap.add_argument("--min-score", type=float, default=0.3)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--mode", choices=["keyword", "vector"], default="keyword")
    args = ap.parse_args()

    items = json.loads((QUESTIONS.parent / args.file).read_text(encoding="utf-8"))
    chunks = build_chunks(size=300)

    passed = refused_ok = answer_total = refuse_total = 0
    total_cost,total_ms = 0.0,0
    rows = []
    model_v, vchunks = s9.load_vectors() if args.mode == "vector" else (None, None)
    for it in items:

        if args.mode == "vector":
            hits = s9.search(it["question"], vchunks, model_v, args.top_k)
        else:
            q_bg = bigrams(it["question"])
            hits = sorted(((score(q_bg, c["text"]), c) for c in chunks),
                          key=lambda x: -x[0])[:args.top_k]
        best = hits[0][0] if hits else 0.0
        t0 = time.perf_counter()
        if best < args.min_score:
            text,usage = "[拒答] 未调用模型", {}
        else:
            context = "\n\n".join(f"[{i}] 来源:{c['source']}\n{c['text']}"
                                  for i ,(_,c) in enumerate(hits,1))

            messages = [
                {"role":"system","content":SYSTEM},
                {"role":"user","content":f"资料：\n{context}\n\n问题：{it['question']}\n\n请依据资料回答并标注 [编号]。"},
            ]
            text,usage = llm.stream_chat(messages,temperature=0.2,max_tokens=400)

        ms = int((time.perf_counter() - t0) * 1000)

        total_ms += ms
        total_cost += llm.cost(usage)
        ok = judge(it, text)

        if it["type"] == "answer":
            answer_total += 1
        else:
            refuse_total += 1
        if ok:
            passed += 1
            if it["type"] == "refuse":
                refused_ok += 1

        rows.append((it["id"],it["type"],ok,best,text.replace("\n"," ")[:46]))

    for rid,typ,ok,best,preview in rows:
        print(f"{rid} {typ:<6} {'✅' if ok else '❌'}  {best:.2f}  {preview}")

    n = len(items)
    print("-" * 72)
    print(f"总准确率 : {passed}/{n} = {passed / n * 100:.0f}%")
    print(f"拒答准确 : {refused_ok}/{refuse_total}")
    print(f"答对/可答 : {passed - refused_ok}/{answer_total}")
    print(f"平均耗时 : {total_ms / n / 1000:.2f}s | 总成本 ${total_cost:.6f} | 阈值 {args.min_score}")

if __name__ == "__main__":
    main()