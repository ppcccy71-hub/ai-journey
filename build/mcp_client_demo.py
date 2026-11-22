#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 客户端测试：启动 mcp_server.py，列出工具并调用一次。

用法：
    python mcp_client_demo.py
"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp_server.py"


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("可用工具：")
            for t in tools.tools:
                desc = (t.description or "").split("\n")[0][:60]
                print(f"  - {t.name}: {desc}")

            print("\n调用 calculator('12*12')：")
            res = await session.call_tool("calculator", {"expression": "12*12"})
            for item in res.content:
                print("  ", getattr(item, "text", item))

            print("\n调用 search_docs('怎么声明请求体', top_k=2)：")
            res = await session.call_tool("search_docs",
                                          {"query": "怎么声明请求体", "top_k": 2})
            for item in res.content:
                print("  ", getattr(item, "text", item)[:200])


if __name__ == "__main__":
    asyncio.run(main())
