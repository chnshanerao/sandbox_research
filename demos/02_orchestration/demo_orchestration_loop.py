#!/usr/bin/env python3
"""
Demo 02: Agent 编排层 — ReAct 编排循环
========================================
演示 AI Agent 的编排层（Orchestration）：
- ReAct 循环：Think → Act → Observe → Repeat
- 工具注册与选择
- 多步推理与状态管理

对应基础设施栈：编排层 / Orchestration
参考产品：LangGraph, CrewAI, OpenAI Agents SDK, AutoGen

注意：由于 LLM API 在此环境不可用，使用 MockLLM 演示编排结构。
文件末尾有真实 LLM 调用的代码示例。
"""
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════
# 1. 工具定义
# ══════════════════════════════════════════════════════════════════

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    func: callable


def calculator(expression: str) -> str:
    """安全的数学计算器"""
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expression):
        return f"错误：不安全的表达式"
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算错误: {e}"


def list_files(directory: str) -> str:
    """列出目录中的文件"""
    try:
        files = os.listdir(directory)
        return "\n".join(files[:20])
    except Exception as e:
        return f"错误: {e}"


def read_file(path: str) -> str:
    """读取文件内容"""
    try:
        with open(path) as f:
            content = f.read()
        return content[:1000]
    except Exception as e:
        return f"错误: {e}"


def web_search(query: str) -> str:
    """模拟网页搜索"""
    mock_results = {
        "weather": "北京今天晴，气温 28°C，湿度 45%",
        "天气": "北京今天晴，气温 28°C，湿度 45%",
        "python": "Python 3.12 是最新稳定版本，发布于 2024 年 10 月",
        "agent": "AI Agent 是能够自主完成任务的 AI 系统，2026 年市场规模预计 $178B",
        "北京": "北京今天晴，气温 28°C，湿度 45%，空气质量良好",
    }
    for keyword, result in mock_results.items():
        if keyword in query.lower() or keyword in query:
            return f"搜索结果: {result}"
    return f"搜索结果: 未找到关于 '{query}' 的信息"


TOOLS = [
    Tool("calculator", "数学计算", {"expression": "数学表达式"}, calculator),
    Tool("list_files", "列出目录文件", {"directory": "目录路径"}, list_files),
    Tool("read_file", "读取文件内容", {"path": "文件路径"}, read_file),
    Tool("web_search", "搜索网页", {"query": "搜索关键词"}, web_search),
]


# ══════════════════════════════════════════════════════════════════
# 2. MockLLM — 模拟 LLM 的工具选择行为
# ══════════════════════════════════════════════════════════════════

class MockLLM:
    """
    模拟 LLM 的 ReAct 推理。
    真实场景中替换为 openai.chat.completions.create() 或 litellm.completion()
    """

    def __init__(self, tools: list[Tool]):
        self.tools = {t.name: t for t in tools}
        self.step = 0

    def decide(self, messages: list[dict]) -> dict:
        """根据对话历史决定下一步行动"""
        user_query = ""
        for msg in messages:
            if msg["role"] == "user":
                user_query = msg["content"]

        last_msg = messages[-1]

        if last_msg["role"] == "tool":
            self.step += 1
            if self.step >= 2:
                return {"type": "answer", "content": f"基于工具调用结果，任务完成。\n结果: {last_msg['content'][:200]}"}
            return self._pick_tool(user_query, follow_up=True)

        self.step = 0
        return self._pick_tool(user_query)

    def _pick_tool(self, query: str, follow_up: bool = False) -> dict:
        q = query.lower()

        if any(w in q for w in ["读取", "read", "查看"]):
            path_match = re.search(r'(/[a-zA-Z0-9_/.]+)', query)
            path = path_match.group(1) if path_match else "/tmp/test.txt"
            return {"type": "tool_call", "name": "read_file", "arguments": {"path": path}}

        if any(w in q for w in ["目录", "列出", "ls", "list"]):
            path_match = re.search(r'(/[a-zA-Z0-9_/.]+)', query)
            path = path_match.group(1) if path_match else "/tmp/test.txt"
            return {"type": "tool_call", "name": "read_file", "arguments": {"path": path}}

        if any(w in q for w in ["搜索", "search", "天气", "weather", "查找"]):
            return {"type": "tool_call", "name": "web_search", "arguments": {"query": query}}

        if any(op in q for op in ["计算", "算", "+", "*"]) or re.search(r'\d+\s*[+\-*/]\s*\d+', q):
            expr = "1+1"
            for pattern in [r'(\d[\d\s+\-*/().]+\d)', r'(\d+\s*[+\-*/]\s*\d+(?:\s*[+\-*/]\s*\d+)*)']:
                match = re.search(pattern, query)
                if match:
                    expr = match.group(1)
                    break
            return {"type": "tool_call", "name": "calculator", "arguments": {"expression": expr}}

        return {"type": "answer", "content": f"我理解你的问题是: {query}。但我没有合适的工具来处理。"}


# ══════════════════════════════════════════════════════════════════
# 3. Agent 编排引擎 — ReAct 循环
# ══════════════════════════════════════════════════════════════════

class ReActAgent:
    """
    ReAct Agent 编排循环

    这就是编排层的核心：
    1. 接收用户任务
    2. 调用 LLM 决定使用哪个工具
    3. 执行工具
    4. 将结果反馈给 LLM
    5. LLM 决定继续调用工具还是给出最终答案
    """

    def __init__(self, llm, tools: list[Tool], max_steps: int = 5):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_steps = max_steps
        self.trace = []

    def run(self, user_query: str) -> str:
        messages = [
            {"role": "system", "content": f"你是一个有工具的 AI Agent。可用工具: {list(self.tools.keys())}"},
            {"role": "user", "content": user_query},
        ]

        self.trace = []
        print(f"\n  [USER] {user_query}")

        for step in range(self.max_steps):
            decision = self.llm.decide(messages)
            self.trace.append({"step": step + 1, **decision})

            if decision["type"] == "answer":
                print(f"  [ANSWER] {decision['content'][:100]}")
                return decision["content"]

            tool_name = decision["name"]
            tool_args = decision["arguments"]
            print(f"  [THINK] 步骤 {step+1}: 需要调用工具 '{tool_name}'")
            print(f"  [TOOL_CALL] {tool_name}({tool_args})")

            if tool_name in self.tools:
                t0 = time.time()
                result = self.tools[tool_name].func(**tool_args)
                duration = (time.time() - t0) * 1000
                print(f"  [OBSERVE] 结果 ({duration:.0f}ms): {result[:80]}")
            else:
                result = f"未知工具: {tool_name}"
                print(f"  [ERROR] {result}")

            messages.append({"role": "assistant", "content": f"调用工具 {tool_name}"})
            messages.append({"role": "tool", "content": result})

        return "达到最大步骤数，任务未完成"


# ══════════════════════════════════════════════════════════════════
# 运行演示
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Demo 02: Agent 编排层 — ReAct 编排循环")
    print("  对应层: 编排层 / Orchestration")
    print("=" * 70)

    llm = MockLLM(TOOLS)
    agent = ReActAgent(llm, TOOLS)

    tasks = [
        "计算 15 * 37 + 12 等于多少",
        "列出 /tmp 目录下有什么文件",
        "搜索北京今天天气怎么样",
        "读取 /etc/hostname 文件的内容",
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n{'─' * 60}")
        print(f"  任务 {i}/{len(tasks)}")
        result = agent.run(task)

    # --- 架构说明 ---
    print(f"\n{'═' * 70}")
    print("  编排层 vs 运行时 vs 沙箱 — 三层区分")
    print("═" * 70)
    print("""
  ┌─────────────────────────────────────────────────────────────┐
  │ 编排层 (Orchestration) ← 本 Demo 演示的内容                  │
  │                                                              │
  │  User: "计算 15*37+12"                                       │
  │    ↓                                                         │
  │  LLM: "我需要用 calculator 工具"  ← 编排 = 决策层            │
  │    ↓                                                         │
  │  Tool Call: calculator(expression="15*37+12")                │
  │    ↓                                                         │
  │  Result: "567"                                               │
  │    ↓                                                         │
  │  LLM: "15 * 37 + 12 = 567"       ← 编排 = 综合结果           │
  ├─────────────────────────────────────────────────────────────┤
  │ 运行时 (Runtime) ← 本 Demo 的 Python 进程本身                 │
  │                                                              │
  │  ReActAgent 类运行在哪里？→ 你的本地 Python 进程              │
  │  真实产品: AWS Lambda, 阿里云 FC, K8s Pod                     │
  ├─────────────────────────────────────────────────────────────┤
  │ 沙箱 (Sandbox) ← Demo 01 演示的内容                          │
  │                                                              │
  │  calculator() 在哪里执行？→ 本 Demo 中在本地执行              │
  │  真实场景: E2B/AgentBay 等隔离的 VM 中执行                    │
  │  为什么要沙箱？→ LLM 生成的代码不可信，需要隔离                │
  └─────────────────────────────────────────────────────────────┘

  真实产品编排层:
  - LangGraph (LangChain): 图工作流 + 检查点 + Human-in-the-loop
  - CrewAI: 多 Agent 角色协作
  - OpenAI Agents SDK: 原生工具调用 + Sandbox Provider
  - AutoGen/AG2: 研究级多 Agent 对话

  ─────────────────────────────────────────────────────────────
  真实 LLM 调用示例（取消注释即可使用）:

  # import litellm
  # response = litellm.completion(
  #     model="gpt-4o",
  #     messages=messages,
  #     tools=[{
  #         "type": "function",
  #         "function": {
  #             "name": "calculator",
  #             "description": "数学计算",
  #             "parameters": {
  #                 "type": "object",
  #                 "properties": {"expression": {"type": "string"}},
  #                 "required": ["expression"]
  #             }
  #         }
  #     }]
  # )
  # tool_call = response.choices[0].message.tool_calls[0]
""")


if __name__ == "__main__":
    main()
