#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Server：把项目的检索与计算能力暴露给任意 MCP 客户端。

启动（stdio）：
    python mcp_server.py

在 Claude Desktop / Cursor 等客户端里配置：
    {
      "mcpServers": {
        "fastapi-docs": {
          "command": "python",
          "args": ["C:/Users/20647/Desktop/AI_WorkPlace/ai-journey/build/mcp_server.py"]
        }
      }
    }
"""
import ast
import operator

from mcp.server.mcpserver import MCPServer

import step9_vector as s9

mcp = MCPServer("fastapi-docs", description="FastAPI 官方文档检索与计算工具")

MODEL_V, CHUNKS = s9.load_vectors()

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}


def _safe_calc(expr):
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("只支持 + - * / ** 和括号")
    return ev(ast.parse(expr, mode="eval").body)


@mcp.tool()
def search_docs(query: str, top_k: int = 5) -> str:
    """在 FastAPI 官方文档中检索，返回最相关的段落和来源文件。

    Args:
        query: 检索问题，中英文均可
        top_k: 返回几段，默认 5
    """
    hits = s9.search_mixed(query, CHUNKS, MODEL_V, top_k, 2, True)
    return "\n\n".join(f"[{c['source']}] {c['text'][:300]}" for _, c in hits)


@mcp.tool()
def calculator(expression: str) -> str:
    """计算算术表达式，支持 + - * / ** 和括号。

    Args:
        expression: 例如 (300*2)/5000
    """
    return str(_safe_calc(expression))


if __name__ == "__main__":
    mcp.run()
