#!/usr/bin/env python3
"""
Demo 03: MCP Server — 协议层演示
==================================
一个简单的 MCP (Model Context Protocol) Server，暴露 3 个工具。

对应基础设施栈：协议层 / Protocols
参考: MCP (Anthropic) — Agent ↔ Tool 集成的事实标准

运行方式: python3 mcp_server.py (由 mcp_client.py 自动启动)
"""
import os
import sys
import json
import math

sys.path.insert(0, "/tmp/sandbox-bench/lib/python3.12/site-packages")

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types


server = Server("demo-mcp-server")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="calculator",
            description="安全的数学计算器，支持加减乘除、幂运算、三角函数",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4' 或 'math.sqrt(144)'"
                    }
                },
                "required": ["expression"],
            },
        ),
        types.Tool(
            name="get_weather",
            description="获取指定城市的天气信息（模拟数据）",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 '北京' 或 'Tokyo'"
                    }
                },
                "required": ["city"],
            },
        ),
        types.Tool(
            name="list_directory",
            description="列出指定目录下的文件和子目录",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径，如 '/tmp'"
                    }
                },
                "required": ["path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "calculator":
        expression = arguments["expression"]
        allowed_names = {"math": math, "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
                         "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log,
                         "abs": abs, "round": round, "pow": pow, "min": min, "max": max}
        try:
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return [types.TextContent(type="text", text=f"计算结果: {expression} = {result}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"计算错误: {e}")]

    elif name == "get_weather":
        city = arguments["city"]
        weather_data = {
            "北京": {"temp": 28, "condition": "晴", "humidity": 45, "wind": "东北风 3级"},
            "上海": {"temp": 32, "condition": "多云", "humidity": 72, "wind": "东南风 4级"},
            "杭州": {"temp": 30, "condition": "阴", "humidity": 68, "wind": "南风 2级"},
            "Tokyo": {"temp": 26, "condition": "Rain", "humidity": 80, "wind": "SW 5km/h"},
        }
        data = weather_data.get(city, {"temp": 25, "condition": "未知", "humidity": 50, "wind": "微风"})
        result = json.dumps({"city": city, **data}, ensure_ascii=False)
        return [types.TextContent(type="text", text=f"天气数据: {result}")]

    elif name == "list_directory":
        path = arguments["path"]
        allowed_prefixes = ["/tmp", "/home"]
        if not any(path.startswith(p) for p in allowed_prefixes):
            return [types.TextContent(type="text", text=f"安全限制: 只允许访问 {allowed_prefixes}")]
        try:
            entries = os.listdir(path)
            result = "\n".join(entries[:20])
            return [types.TextContent(type="text", text=f"目录 {path} 内容:\n{result}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"错误: {e}")]

    return [types.TextContent(type="text", text=f"未知工具: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
