#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 桥：把外部 MCP Server 的工具接入本地 Agent。

配置在 mcp_servers.json：
    {"servers": [{"name": "time", "command": "python", "args": ["-m", "mcp_server_time"]}]}

每次调用都是短连接（启动 server → 调用 → 退出），简单但慢；
生产应改为长连接 + 后台事件循环。
"""
import asyncio
import json
import sys
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:              # 没装 mcp 时降级：Agent 仍可用本地工具
    ClientSession = StdioServerParameters = stdio_client = None
    MCP_AVAILABLE = False

CONFIG = Path(__file__).resolve().parent / "mcp_servers.json"


def load_servers():
    if not CONFIG.exists():
        return []
    return json.loads(CONFIG.read_text(encoding="utf-8")).get("servers", [])


def _params(server):
    return StdioServerParameters(
        command=server.get("command", sys.executable),
        args=server.get("args", []),
        cwd=server.get("cwd"),
    )


async def _list_one(server):
    async with stdio_client(_params(server)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_tools()
            return [t.model_dump() for t in res.tools]


async def _call_one(server, tool, args):
    async with stdio_client(_params(server)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(tool, args)
            texts = [getattr(item, "text", str(item)) for item in res.content]
            return "\n".join(texts)


def external_tools():
    """返回 [{schema, server, tool}]，schema 已转成 OpenAI/DeepSeek 格式。"""
    out = []
    if not MCP_AVAILABLE:
        return out
    for server in load_servers():
        name = server["name"]
        try:
            tools = asyncio.run(_list_one(server))
        except Exception as e:
            print(f"[MCP] {name} 连接失败：{e}")
            continue
        for t in tools:
            # mcp 2.x 用 input_schema，1.x 用 inputSchema，两个都兼容
            params = t.get("input_schema") or t.get("inputSchema") or {"type": "object", "properties": {}}
            out.append({
                "server": name,
                "tool": t["name"],
                "schema": {
                    "type": "function",
                    "function": {
                        "name": f"{name}__{t['name']}",
                        "description": (t.get("description") or "")[:300],
                        "parameters": params,
                    },
                },
            })
        print(f"[MCP] {name}：{len(tools)} 个工具 {[t['name'] for t in tools]}")
    return out


def call(server_name, tool_name, args):
    server = next((s for s in load_servers() if s["name"] == server_name), None)
    if not server:
        return f"MCP 服务不存在：{server_name}"
    try:
        return asyncio.run(_call_one(server, tool_name, args))
    except Exception as e:
        return f"MCP 调用失败：{type(e).__name__}: {e}"
