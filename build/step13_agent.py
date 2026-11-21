#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""step12：最小 Agent —— 会查资料、会算数。"""
import argparse
import ast
import json
import operator
import os
import urllib.request
from pathlib import Path

import step9_vector as s9

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("AGENT_WORKSPACE") or (ROOT / "agent_workspace"))
WORKSPACE.mkdir(exist_ok=True)

CALL_LOG = []                      # ← 加这一行

ENV = Path(__file__).resolve().parent.parent / ".env"

def safe_path(name):
    """把模型给的文件名限制在工作区内，防止 ../../ 越界。"""
    p = (WORKSPACE / name).resolve()
    if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
        raise ValueError("路径越界：只允许操作 agent_workspace 内的文件")
    return p


def load_env():
    if not ENV.exists():          # Docker 里没有 .env，配置由环境变量注入
        return
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


load_env()
BASE = os.environ["LLM_BASE_URL"].rstrip("/")
KEY = os.environ["LLM_API_KEY"]
MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
MODEL_V, CHUNKS = s9.load_vectors()

SYSTEM = ("你是一个会使用工具的助手。需要查资料时调用 search_docs，"
          "需要算数时调用 calculator。不要编造资料里没有的内容。")

TOOLS = [
    {"type": "function", "function": {
        "name": "search_docs",
        "description": "在本地知识库里搜索相关资料，返回最相关的几段文字",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calculator",
        "description": "计算数学表达式，支持 + - * / ** 和括号",
        "parameters": {"type": "object",
                       "properties": {"expression": {"type": "string", "description": "例如 (300*2)/5000"}},
                       "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "把内容写入工作区里的文件（覆盖写）",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "文件名，如 report.md"},
                                      "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取工作区里的文件",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "list_files",
        "description": "列出工作区里的文件",
        "parameters": {"type": "object", "properties": {}}}},
]

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}


def safe_calc(expr):
    """不用 eval，用 AST 只允许四则运算和乘方。"""
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("表达式里包含不允许的运算")
    return ev(ast.parse(expr, mode="eval").body)


def execute(name, args):
    """执行工具。任何异常都转成文字返回给模型，不让程序崩。"""
    try:
        if name == "search_docs":
            hits = s9.search(args["query"], CHUNKS, MODEL_V, 3)
            return "\n\n".join(f"[{c['source']}] {c['text'][:200]}" for _, c in hits)
        if name == "calculator":
            return str(safe_calc(args["expression"]))
        if name == "write_file":
            p = safe_path(args["path"])
            p.write_text(args["content"], encoding="utf-8")
            return f"已写入 {p.name}（{len(args['content'])} 字）"
        if name == "read_file":
            p = safe_path(args["path"])
            if not p.exists():
                return f"文件不存在：{p.name}"
            return p.read_text(encoding="utf-8")[:2000]
        if name == "list_files":
            files = sorted(p.name for p in WORKSPACE.iterdir() if p.is_file())
            return "、".join(files) if files else "（工作区是空的）"
        return f"错误：没有名为 {name} 的工具"
    except Exception as e:
        return f"工具执行失败：{type(e).__name__}: {e}"


def chat(messages):
    body = {"model": MODEL, "messages": messages, "temperature": 0.2,
            "max_tokens": 500, "thinking": {"type": "disabled"}, "tools": TOOLS}
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST")
    with _OPENER.open(req, timeout=120) as r:
        return json.loads(r.read().decode())


def run(question, max_steps=6, trace=None):
    CALL_LOG.clear()
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": question}]
    for step in range(1, max_steps + 1):
        resp = chat(messages)
        msg = resp["choices"][0]["message"]
        reason = resp["choices"][0]["finish_reason"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        print(f"[第 {step} 轮] finish_reason={reason} 工具调用={len(calls)}")

        if not calls:
            return msg.get("content") or "（模型没有返回内容）"

        for c in calls:
            name = c["function"]["name"]
            CALL_LOG.append(name)
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
                result = "错误：参数不是合法 JSON"
            else:
                result = execute(name, args)
            if trace is not None:
                trace.append({"step": step, "tool": name, "args": args,
                              "result": result[:160]})
            print(f"   → {name}({json.dumps(args, ensure_ascii=False)[:60]})")
            print(f"   → {name}({json.dumps(args, ensure_ascii=False)[:60]})")
            print(f"     ← {result[:70].replace(chr(10), ' ')}")
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})

    return "（超过最大轮数，任务未完成）"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--max-steps", type=int, default=5)
    args = ap.parse_args()
    print(f"问题：{args.question}\n")
    print("\n最终回答：", run(args.question, args.max_steps))