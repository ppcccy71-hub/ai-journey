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

import mcp_bridge
import finance_tools
import market
import numpy_tool
import web_tools
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
BASE = (os.environ.get("LLM_BASE_URL") or "").rstrip("/")
KEY = os.environ.get("LLM_API_KEY") or ""
MODEL = os.environ.get("LLM_MODEL", "deepseek-flash")
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
MODEL_V, CHUNKS = s9.load_vectors()

SYSTEM = ("你是一个会使用工具的金融助手。查合规资料用 search_docs，查行情用 stock_quote，"
          "金融计算用 finance_calc（复利/贷款/NPV/IRR/CAGR/持仓盈亏）。"
          "不要编造资料里没有的内容；不要给买卖建议。")

LOCAL_TOOLS = [
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
        "name": "numpy_calc",
        "description": "用 numpy 计算数组、矩阵和统计量。支持 np.mean/std/sum/dot/norm、矩阵乘法 @、.T、.shape、reshape 等",
        "parameters": {"type": "object",
                       "properties": {"expression": {"type": "string",
                                                     "description": "numpy 表达式，例如 np.mean([1,2,3,4]) 或 np.array([[1,2],[3,4]]) @ np.array([[1],[0]])"}},
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
    {"type": "function", "function": {
        "name": "web_search",
        "description": "联网搜索，返回标题、链接和摘要。适合查最新信息或本地知识库没有的内容",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string", "description": "搜索词"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "fetch_url",
        "description": "抓取一个网页的正文，返回标题和文本",
        "parameters": {"type": "object",
                       "properties": {"url": {"type": "string", "description": "http/https 链接"}},
                       "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "finance_calc",
        "description": "金融计算：复利、等额本息/本金贷款、NPV、IRR、CAGR、持仓盈亏",
        "parameters": {"type": "object",
                       "properties": {
                           "kind": {"type": "string",
                                    "enum": ["compound", "loan", "npv", "irr", "cagr", "position"]},
                           "params": {"type": "object",
                                      "description": "参数。compound: {principal, rate, years, times}; "
                                                     "loan: {principal, rate, years, method}; "
                                                     "npv/irr: {rate, cashflows}; "
                                                     "cagr: {begin, end, years}; "
                                                     "position: {cost, price, shares}"}},
                       "required": ["kind", "params"]}}},
    {"type": "function", "function": {
        "name": "stock_quote",
        "description": "查询 A 股实时行情：价格、涨跌幅、振幅、换手率、成交额",
        "parameters": {"type": "object",
                       "properties": {"symbol": {"type": "string", "description": "6 位代码，如 600519"}},
                       "required": ["symbol"]}}},
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


_EXTERNAL = None


def external_tools():
    """懒加载外部 MCP 工具，避免拖慢应用启动。"""
    global _EXTERNAL
    if _EXTERNAL is None:
        _EXTERNAL = mcp_bridge.external_tools()
    return _EXTERNAL


def all_tools():
    return LOCAL_TOOLS + [e["schema"] for e in external_tools()]


def execute(name, args, approve=None):
    for e in external_tools():
        if e["schema"]["function"]["name"] == name:
            return mcp_bridge.call(e["server"], e["tool"], args)
    """执行工具。任何异常都转成文字返回给模型，不让程序崩。"""
    try:
        if name == "search_docs":
            hits = s9.search(args["query"], CHUNKS, MODEL_V, 3)
            return "\n\n".join(f"[{c['source']}] {c['text'][:200]}" for _, c in hits)
        if name == "calculator":
            return str(safe_calc(args["expression"]))
        if name == "numpy_calc":
            return numpy_tool.evaluate(args["expression"])
        if name == "write_file":
            if approve is not None and not approve(name, args):
                return "用户拒绝执行写入，文件未创建"
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
        if name == "web_search":
            results = web_tools.search(args["query"], limit=5)
            if not results:
                return "没有搜到结果（可能是网络或搜索引擎限制）"
            return "\n\n".join(f"{r['title']}\n{r['url']}\n{r['snippet']}" for r in results)
        if name == "fetch_url":
            page = web_tools.fetch(args["url"], max_chars=1500)
            return f"{page['title']}\n{page['text']}"
        if name == "finance_calc":
            return finance_tools.calculate(args["kind"], args.get("params") or {})
        if name == "stock_quote":
            quotes = market.fetch([args["symbol"]])
            if not quotes:
                return "没有查到该股票的行情"
            q = quotes[0]
            return (f"{q['name']}（{q['symbol']}）现价 {q['price']}，涨跌幅 {q['change_pct']:+.2f}%，"
                    f"振幅 {q['amplitude']:.2f}%，换手率 {q['turnover']:.2f}%，成交额 {q['amount']:.0f} 万元")
        return f"错误：没有名为 {name} 的工具"
    except Exception as e:
        return f"工具执行失败：{type(e).__name__}: {e}"


def chat(messages):
    if not BASE or not KEY:
        raise RuntimeError("未配置 LLM_BASE_URL / LLM_API_KEY，Agent 无法调用模型")
    body = {"model": MODEL, "messages": messages, "temperature": 0.2,
            "max_tokens": 1200, "thinking": {"type": "disabled"}, "tools": all_tools()}
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST")
    with _OPENER.open(req, timeout=120) as r:
        return json.loads(r.read().decode())


def run(question, max_steps=6, trace=None, on_event=None, approve=None, history=None):
    """执行任务。

    on_event: 收到事件的回调（step / tool_call / tool_result / answer）
    approve:  写操作前的人类确认回调，返回 True 才执行
    history:  最近几轮对话，用于追问
    """
    CALL_LOG.clear()
    messages = [{"role": "system", "content": SYSTEM}]
    if history:
        messages.extend({"role": h["role"], "content": h["content"]} for h in history[-4:])
    messages.append({"role": "user", "content": question})

    def emit(event):
        if on_event:
            on_event(event)

    for step in range(1, max_steps + 1):
        resp = chat(messages)
        msg = resp["choices"][0]["message"]
        reason = resp["choices"][0]["finish_reason"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        print(f"[第 {step} 轮] finish_reason={reason} 工具调用={len(calls)}")
        emit({"type": "step", "step": step, "finish_reason": reason, "tool_calls": len(calls)})

        if not calls:
            answer = msg.get("content") or "（模型没有返回内容）"
            emit({"type": "answer", "text": answer})
            return answer

        for c in calls:
            name = c["function"]["name"]
            CALL_LOG.append(name)
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
                result = "错误：参数不是合法 JSON"
                emit({"type": "tool_call", "step": step, "tool": name, "args": {}})
            else:
                emit({"type": "tool_call", "step": step, "tool": name, "args": args})
                result = execute(name, args, approve)

            if trace is not None:
                trace.append({"step": step, "tool": name, "args": args,
                              "result": result[:160]})
            emit({"type": "tool_result", "step": step, "tool": name, "result": result[:300]})
            print(f"   → {name}({json.dumps(args, ensure_ascii=False)[:60]})")
            print(f"     ← {result[:70].replace(chr(10), ' ')}")
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})

    answer = "（超过最大轮数，任务未完成）"
    emit({"type": "answer", "text": answer})
    return answer


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--max-steps", type=int, default=5)
    args = ap.parse_args()
    print(f"问题：{args.question}\n")
    print("\n最终回答：", run(args.question, args.max_steps))