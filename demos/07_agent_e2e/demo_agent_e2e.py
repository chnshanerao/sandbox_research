#!/usr/bin/env python3
"""
Demo 07: 全栈 Agent — 编排 + 安全 + 沙箱 + 追踪
==================================================
将所有基础设施层组合在一起，演示一个完整的 Agent 执行流程：

  编排层: ReAct 循环决定执行步骤
  安全层: 工具授权策略拦截
  沙箱层: AgentBay 云端 VM 执行代码
  可观测性: OpenTelemetry 追踪全链路

对应基础设施栈：全栈组合
"""
import os
import sys
import time
import json
import re

sys.path.insert(0, "/tmp/sandbox-bench/lib/python3.12/site-packages")
os.environ.setdefault("AGENTBAY_API_KEY", "akm-3d21e663-3224-4cee-ae77-a6c6c7ccb6d7")
os.environ.setdefault("AGENTBAY_LOG_LEVEL", "WARNING")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

from agentbay import AgentBay
from agentbay._common.params.session_params import CreateSessionParams


# ══════════════════════════════════════════════════════════════════
# 1. 可观测性层 — Trace 设置
# ══════════════════════════════════════════════════════════════════

class TraceCollector:
    def __init__(self):
        self.spans = []

    def export(self, spans):
        for span in spans:
            self.spans.append({
                "name": span.name,
                "duration_ms": round((span.end_time - span.start_time) / 1e6, 1),
                "attributes": dict(span.attributes) if span.attributes else {},
                "parent": span.parent.span_id if span.parent else None,
                "span_id": span.context.span_id,
            })
        return True

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=0):
        return True

    def print_trace(self):
        spans_reversed = list(reversed(self.spans))
        roots = [s for s in spans_reversed if s["parent"] is None]
        for root in roots:
            self._print(root, spans_reversed, 0)

    def _print(self, span, all_spans, indent):
        prefix = "  " + "│ " * indent + "├─ " if indent > 0 else "  "
        attrs = span["attributes"]
        extra = ""
        if "tool.name" in attrs:
            extra = f" [{attrs['tool.name']}]"
        if "auth.result" in attrs:
            extra += f" auth={attrs['auth.result']}"
        if "sandbox.command" in attrs:
            cmd = str(attrs["sandbox.command"])[:40]
            extra += f" cmd='{cmd}'"
        print(f"{prefix}{span['name']} ({span['duration_ms']}ms){extra}")
        children = [s for s in all_spans if s["parent"] == span["span_id"]]
        for child in children:
            self._print(child, all_spans, indent + 1)


# ══════════════════════════════════════════════════════════════════
# 2. 安全层 — 工具授权
# ══════════════════════════════════════════════════════════════════

class AuthPolicy:
    ALLOWED = {"sandbox_shell", "sandbox_python", "sandbox_read_file", "sandbox_write_file", "calculator"}
    DENIED_COMMANDS = ["rm -rf", "shutdown", "reboot", "mkfs", "dd if="]

    def check(self, tool_name: str, arguments: dict) -> tuple[bool, str]:
        if tool_name not in self.ALLOWED:
            return False, f"工具 '{tool_name}' 未授权"
        if tool_name == "sandbox_shell":
            cmd = arguments.get("command", "")
            for bad in self.DENIED_COMMANDS:
                if bad in cmd:
                    return False, f"危险命令被拦截: '{bad}'"
        return True, "OK"


# ══════════════════════════════════════════════════════════════════
# 3. 沙箱层 — AgentBay 工具
# ══════════════════════════════════════════════════════════════════

class SandboxTools:
    def __init__(self, session):
        self.session = session

    def sandbox_shell(self, command: str) -> str:
        result = self.session.command.execute_command(command)
        return getattr(result, 'stdout', str(result)).strip()

    def sandbox_python(self, code: str) -> str:
        escaped = code.replace('"', '\\"')
        result = self.session.command.execute_command(f'python3 -c "{escaped}"')
        return getattr(result, 'stdout', str(result)).strip()

    def sandbox_write_file(self, path: str, content: str) -> str:
        self.session.file_system.write_file(path, content)
        return f"写入 {len(content)} 字符到 {path}"

    def sandbox_read_file(self, path: str) -> str:
        result = self.session.file_system.read_file(path)
        return str(result).strip()[:500]

    def calculator(self, expression: str) -> str:
        allowed = set("0123456789+-*/(). ")
        if all(c in allowed for c in expression):
            return str(eval(expression))
        return "不安全的表达式"


# ══════════════════════════════════════════════════════════════════
# 4. 编排层 — 任务编排
# ══════════════════════════════════════════════════════════════════

TASK_PLAN = [
    {
        "step": 1,
        "think": "先在沙箱中生成 Fibonacci 数列",
        "tool": "sandbox_shell",
        "args": {"command": "python3 -c 'fibs=[0,1]\nfor i in range(18): fibs.append(fibs[-1]+fibs[-2])\nprint(fibs)'"},
    },
    {
        "step": 2,
        "think": "将结果写入文件",
        "tool": "sandbox_write_file",
        "args": {"path": "/tmp/fibonacci.txt", "content": ""},  # content filled from step 1
    },
    {
        "step": 3,
        "think": "验证文件已写入",
        "tool": "sandbox_read_file",
        "args": {"path": "/tmp/fibonacci.txt"},
    },
    {
        "step": 4,
        "think": "统计文件字节数",
        "tool": "sandbox_shell",
        "args": {"command": "wc -c /tmp/fibonacci.txt && echo 'Done!'"},
    },
    {
        "step": 5,
        "think": "尝试危险命令 (应被安全层拦截)",
        "tool": "sandbox_shell",
        "args": {"command": "rm -rf /tmp/fibonacci.txt"},
    },
]


# ══════════════════════════════════════════════════════════════════
# 运行
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Demo 07: 全栈 Agent — 编排 + 安全 + 沙箱 + 追踪")
    print("  组合: 编排层 + 安全层 + 沙箱层 + 可观测性层")
    print("=" * 70)

    print("""
  本 Demo 将所有基础设施层串联起来：
  1. 编排层: 按预设步骤执行任务 (真实场景由 LLM 驱动)
  2. 安全层: 检查每个工具调用是否授权
  3. 沙箱层: 在 AgentBay 云端 VM 中执行命令
  4. 可观测性: OpenTelemetry 追踪全链路
""")

    # --- 初始化各层 ---
    collector = TraceCollector()
    provider = TracerProvider(resource=Resource.create({"service.name": "e2e-agent"}))
    provider.add_span_processor(SimpleSpanProcessor(collector))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("e2e-agent")

    auth = AuthPolicy()
    agent_bay = None
    session = None

    try:
        # --- 创建沙箱 ---
        print("[0] 初始化沙箱")
        print("-" * 40)
        with tracer.start_as_current_span("sandbox.create") as span:
            agent_bay = AgentBay(api_key=os.environ["AGENTBAY_API_KEY"])
            params = CreateSessionParams(image_id="computer-use-ubuntu-2204")
            result = agent_bay.create(params=params)
            if not result.success:
                print(f"  [FAIL] {result.error_message}")
                return
            session = result.session
            span.set_attribute("sandbox.session_id", session.session_id)
            print(f"  [OK] Session: {session.session_id}")

        tools = SandboxTools(session)
        last_result = ""

        # --- 执行任务 ---
        print(f"\n[1] 执行多步任务: 生成 Fibonacci → 写文件 → 验证 → 统计")
        print("-" * 40)

        with tracer.start_as_current_span("agent.run") as agent_span:
            agent_span.set_attribute("agent.task", "Generate Fibonacci, write to file, verify")

            for plan in TASK_PLAN:
                step = plan["step"]
                tool_name = plan["tool"]
                args = dict(plan["args"])

                if step == 2 and last_result:
                    args["content"] = last_result

                print(f"\n  Step {step}: {plan['think']}")

                # 安全层检查
                with tracer.start_as_current_span("auth.check") as auth_span:
                    allowed, reason = auth.check(tool_name, args)
                    auth_span.set_attribute("auth.tool", tool_name)
                    auth_span.set_attribute("auth.result", "ALLOW" if allowed else "DENY")
                    auth_span.set_attribute("auth.reason", reason)

                if not allowed:
                    print(f"  [DENY] 安全层拦截: {reason}")
                    continue

                # 沙箱执行
                with tracer.start_as_current_span("tool.execute") as tool_span:
                    tool_span.set_attribute("tool.name", tool_name)
                    if "command" in args:
                        tool_span.set_attribute("sandbox.command", args["command"])

                    t0 = time.time()
                    func = getattr(tools, tool_name)
                    result = func(**args)
                    duration = (time.time() - t0) * 1000

                    tool_span.set_attribute("tool.duration_ms", round(duration, 1))
                    tool_span.set_attribute("tool.result_preview", str(result)[:100])

                    last_result = result
                    result_preview = str(result)[:80]
                    print(f"  [OK] {tool_name} → {result_preview} ({duration:.0f}ms)")

        # --- Trace 输出 ---
        print(f"\n{'═' * 70}")
        print("[2] 全链路追踪 (OpenTelemetry Trace)")
        print("-" * 40)
        collector.print_trace()

        # --- 架构总览 ---
        print(f"\n{'═' * 70}")
        print("  全栈 Agent 架构总览")
        print("═" * 70)
        print("""
  本 Demo 演示的完整链路:

  User Task
    ↓
  ┌─── 编排层 ──────────────────────────────────────────────┐
  │  Step 1: 生成 Fibonacci                                  │
  │  Step 2: 写入文件                                        │
  │  Step 3: 验证文件                                        │
  │  Step 4: 统计字节数                                      │
  │  Step 5: 尝试删除 (被安全层拦截)                          │
  └──────────────┬──────────────────────────────────────────┘
                 ↓ tool_call
  ┌─── 安全层 ──────────────────────────────────────────────┐
  │  白名单检查 → 危险命令检测 → ALLOW / DENY               │
  └──────────────┬──────────────────────────────────────────┘
                 ↓ (if ALLOW)
  ┌─── 沙箱层 (AgentBay) ──────────────────────────────────┐
  │  Cloud VM: Ubuntu 22.04, 4C/7G/99G                      │
  │  Python 代码在 VM 内执行, 文件在 VM 内读写               │
  │  与宿主完全隔离                                          │
  └─────────────────────────────────────────────────────────┘
                 ↓
  ┌─── 可观测性 (OpenTelemetry) ───────────────────────────┐
  │  每个操作记录 Span: 耗时、属性、父子关系                 │
  │  真实场景: 上报到 Braintrust / Langfuse / LangSmith     │
  └─────────────────────────────────────────────────────────┘
""")

    except Exception as e:
        print(f"\n  [ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if session and agent_bay:
            print("[3] 清理沙箱")
            with tracer.start_as_current_span("sandbox.destroy"):
                agent_bay.delete(session)
                print("  [OK] Session 已销毁")

        provider.shutdown()


if __name__ == "__main__":
    main()
