#!/usr/bin/env python3
"""
Demo 03: MCP Client — 连接 MCP Server 并调用工具
==================================================
演示 MCP (Model Context Protocol) 的客户端：
- 通过 stdio 传输层连接 MCP Server
- 发现可用工具（list_tools）
- 调用工具并获取结果

对应基础设施栈：协议层 / Protocols
参考: MCP (Anthropic) — 被 AWS、数千个开源项目采用的 Agent 协议

运行方式: python3 mcp_client.py
"""
import os
import sys
import asyncio
import json

sys.path.insert(0, "/tmp/sandbox-bench/lib/python3.12/site-packages")

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    print("=" * 70)
    print("  Demo 03: MCP 协议层 — Server + Client 交互")
    print("  对应层: 协议层 / Protocols")
    print("=" * 70)

    print("""
  MCP (Model Context Protocol) 是 Anthropic 发布的开放协议
  定位: Agent ↔ Tool/数据源 的标准化接口
  类比: USB 接口 — 让任何 Agent 接入任何工具

  本 Demo 启动一个 MCP Server (暴露 3 个工具)，
  然后用 MCP Client 连接并调用它们。
""")

    server_script = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    python_path = sys.executable

    server_params = StdioServerParameters(
        command=python_path,
        args=[server_script],
        env={
            **os.environ,
            "PYTHONPATH": "/tmp/sandbox-bench/lib/python3.12/site-packages",
        },
    )

    print("[1] 连接 MCP Server (stdio 传输)")
    print("-" * 40)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"  [OK] MCP Session 建立成功")
            print(f"  传输方式: stdio (Server 作为子进程)")

            # --- 工具发现 ---
            print(f"\n[2] 工具发现 (list_tools)")
            print("-" * 40)
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"  发现 {len(tools)} 个工具:")
            for tool in tools:
                params = list(tool.inputSchema.get("properties", {}).keys())
                print(f"    - {tool.name}: {tool.description[:40]}  参数: {params}")

            # --- 调用工具 ---
            print(f"\n[3] 工具调用 (call_tool)")
            print("-" * 40)

            test_calls = [
                ("calculator", {"expression": "2 ** 10 + math.sqrt(144)"}),
                ("calculator", {"expression": "math.pi * 3.5 ** 2"}),
                ("get_weather", {"city": "北京"}),
                ("get_weather", {"city": "上海"}),
                ("list_directory", {"path": "/tmp"}),
                ("list_directory", {"path": "/etc/secret"}),
            ]

            for tool_name, arguments in test_calls:
                result = await session.call_tool(tool_name, arguments)
                text = result.content[0].text if result.content else "无结果"
                arg_str = json.dumps(arguments, ensure_ascii=False)
                print(f"\n  {tool_name}({arg_str})")
                for line in text.split("\n")[:3]:
                    print(f"    → {line}")

    # --- 架构说明 ---
    print(f"\n{'═' * 70}")
    print("  MCP 在 Agent 架构中的位置")
    print("═" * 70)
    print("""
  ┌───────────────────────────────────────────────────────────┐
  │  Agent (LLM)                                              │
  │    "我需要查天气"                                          │
  │      ↓                                                    │
  │  MCP Client  ←──── MCP 协议 ────→  MCP Server            │
  │  (Agent 侧)     JSON-RPC/stdio     (工具侧)              │
  │                                                           │
  │  调用流程:                                                 │
  │  1. Client → Server: list_tools (发现可用工具)             │
  │  2. Client → Server: call_tool("get_weather", {city:..})  │
  │  3. Server → Client: 返回工具执行结果                      │
  │  4. Agent 拿到结果，继续推理                               │
  └───────────────────────────────────────────────────────────┘

  MCP vs A2A vs ACP:
  ┌──────────┬─────────────────┬──────────────────────────────┐
  │ 协议      │ 定位             │ 采用情况                    │
  ├──────────┼─────────────────┼──────────────────────────────┤
  │ MCP      │ Agent ↔ 工具     │ 最广泛 (AWS GA, 数千 Server) │
  │ A2A      │ Agent ↔ Agent   │ Google 发布, 与 MCP 互补     │
  │ ACP      │ 企业 Agent 通信  │ IBM 推动, 企业场景           │
  │ ASL      │ Agent 安全链路   │ 蚂蚁集团, 聚焦安全          │
  └──────────┴─────────────────┴──────────────────────────────┘
""")


if __name__ == "__main__":
    asyncio.run(main())
