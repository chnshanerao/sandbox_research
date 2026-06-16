#!/usr/bin/env python3
"""
Demo 04: 可观测性层 — OpenTelemetry Agent 追踪
================================================
演示 AI Agent 基础设施的可观测性层：
- Span 追踪：Agent 运行 → LLM 调用 → 工具执行
- 自定义属性：模型、Token 用量、工具名称
- 父子关系：嵌套 Span 展示调用链

对应基础设施栈：可观测性 / Observability
参考产品：Braintrust ($80M B轮), LangSmith, Langfuse, Arize

运行方式: python3 demo_observability.py
"""
import sys
import time
import json
import random

sys.path.insert(0, "/tmp/sandbox-bench/lib/python3.12/site-packages")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource


# ══════════════════════════════════════════════════════════════════
# 1. 设置 OpenTelemetry
# ══════════════════════════════════════════════════════════════════

class PrettyExporter:
    """自定义 Span 导出器 — 格式化输出 Agent 调用链"""

    def __init__(self):
        self.spans = []

    def export(self, spans):
        for span in spans:
            self.spans.append({
                "name": span.name,
                "duration_ms": round((span.end_time - span.start_time) / 1e6, 1),
                "attributes": dict(span.attributes) if span.attributes else {},
                "status": span.status.status_code.name,
                "parent": span.parent.span_id if span.parent else None,
                "span_id": span.context.span_id,
            })
        return True

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=0):
        return True

    def print_trace(self):
        if not self.spans:
            print("  (无 Span 数据)")
            return

        spans_reversed = list(reversed(self.spans))
        root_spans = [s for s in spans_reversed if s["parent"] is None]

        for root in root_spans:
            self._print_span(root, spans_reversed, indent=0)

    def _print_span(self, span, all_spans, indent):
        prefix = "  " + "│ " * indent + "├─ " if indent > 0 else "  "
        attrs = span["attributes"]
        extra = ""
        if "llm.model" in attrs:
            extra = f" [model={attrs['llm.model']}]"
        if "llm.tokens_in" in attrs:
            extra += f" [tokens: {attrs['llm.tokens_in']}→{attrs['llm.tokens_out']}]"
        if "tool.name" in attrs:
            extra += f" [tool={attrs['tool.name']}]"
        if "tool.result" in attrs:
            result_str = str(attrs["tool.result"])[:40]
            extra += f" → {result_str}"

        print(f"{prefix}{span['name']} ({span['duration_ms']}ms){extra}")

        children = [s for s in all_spans if s["parent"] == span["span_id"]]
        for child in children:
            self._print_span(child, all_spans, indent + 1)


# ══════════════════════════════════════════════════════════════════
# 2. 模拟 Agent 运行
# ══════════════════════════════════════════════════════════════════

def simulate_llm_call(tracer, model, prompt, response_text, tokens_in=100, tokens_out=50):
    """模拟一次 LLM 调用"""
    with tracer.start_as_current_span("llm.call") as span:
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.tokens_in", tokens_in)
        span.set_attribute("llm.tokens_out", tokens_out)
        span.set_attribute("llm.prompt_preview", prompt[:50])
        time.sleep(random.uniform(0.05, 0.15))
        span.set_attribute("llm.response_preview", response_text[:50])
        return response_text


def simulate_tool_call(tracer, tool_name, arguments, result):
    """模拟一次工具调用"""
    with tracer.start_as_current_span("tool.call") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("tool.arguments", json.dumps(arguments, ensure_ascii=False))
        time.sleep(random.uniform(0.02, 0.08))
        span.set_attribute("tool.result", str(result)[:100])
        return result


def run_agent_task(tracer, task: str):
    """模拟完整的 Agent 任务执行"""
    with tracer.start_as_current_span("agent.run") as span:
        span.set_attribute("agent.task", task)
        span.set_attribute("agent.max_steps", 5)

        llm_response = simulate_llm_call(
            tracer, "claude-sonnet-4-6",
            f"Task: {task}\nAvailable tools: calculator, web_search",
            "I'll use the calculator tool to compute this.",
            tokens_in=150, tokens_out=30,
        )

        tool_result = simulate_tool_call(
            tracer, "calculator",
            {"expression": "15 * 37 + 12"},
            "567",
        )

        final_response = simulate_llm_call(
            tracer, "claude-sonnet-4-6",
            f"Tool result: {tool_result}. Generate final answer.",
            f"The answer is {tool_result}.",
            tokens_in=80, tokens_out=20,
        )

        span.set_attribute("agent.result", final_response)
        span.set_attribute("agent.steps", 3)
        span.set_attribute("agent.total_tokens", 280)
        return final_response


# ══════════════════════════════════════════════════════════════════
# 运行演示
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Demo 04: 可观测性层 — OpenTelemetry Agent 追踪")
    print("  对应层: 可观测性 / Observability")
    print("=" * 70)

    print("""
  为什么需要可观测性？
  Agent 是多步推理系统 — 每次 LLM 调用、每次工具调用都是黑盒
  可观测性让你看到：调用链、延迟、Token 用量、错误点
""")

    # 设置 Tracer
    exporter = PrettyExporter()
    resource = Resource.create({"service.name": "demo-agent"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("demo-agent-tracer")

    # --- 1. 运行 Agent ---
    print("[1] 执行 Agent 任务 (带 Trace)")
    print("-" * 40)

    tasks = [
        "计算 15 * 37 + 12",
        "搜索北京天气并汇总",
    ]

    for task in tasks:
        print(f"\n  任务: {task}")
        result = run_agent_task(tracer, task)
        print(f"  结果: {result}")

    # --- 2. 展示 Trace ---
    print(f"\n[2] 调用链追踪 (Trace Tree)")
    print("-" * 40)
    exporter.print_trace()

    # --- 3. 指标汇总 ---
    print(f"\n[3] 指标汇总")
    print("-" * 40)

    total_duration = sum(s["duration_ms"] for s in exporter.spans if s["parent"] is None)
    llm_calls = [s for s in exporter.spans if s["name"] == "llm.call"]
    tool_calls = [s for s in exporter.spans if s["name"] == "tool.call"]
    total_tokens = sum(
        s["attributes"].get("llm.tokens_in", 0) + s["attributes"].get("llm.tokens_out", 0)
        for s in llm_calls
    )

    print(f"  Agent 运行总数:  {len(tasks)}")
    print(f"  LLM 调用次数:    {len(llm_calls)}")
    print(f"  工具调用次数:    {len(tool_calls)}")
    print(f"  总 Token 消耗:   {total_tokens}")
    print(f"  总执行时间:      {total_duration:.0f}ms")
    print(f"  平均 LLM 延迟:   {sum(s['duration_ms'] for s in llm_calls)/len(llm_calls):.0f}ms")

    # --- 架构说明 ---
    print(f"\n{'═' * 70}")
    print("  可观测性在 Agent 架构中的位置")
    print("═" * 70)
    print("""
  Agent 执行流程（带追踪）:

  agent.run ──────────────────────────────────────── 350ms
  │
  ├─ llm.call [claude-sonnet-4-6] ─────────────── 120ms
  │    tokens_in=150, tokens_out=30
  │
  ├─ tool.call [calculator] ──────────────────────  45ms
  │    expression="15*37+12" → "567"
  │
  └─ llm.call [claude-sonnet-4-6] ─────────────── 100ms
       tokens_in=80, tokens_out=20

  可观测性产品对比:
  ┌──────────────┬────────────────┬────────────────────────┐
  │ 产品          │ 融资/动态       │ 特色                   │
  ├──────────────┼────────────────┼────────────────────────┤
  │ Braintrust   │ $80M B轮       │ 评估驱动，自动 Trace    │
  │ LangSmith    │ LangChain 内置 │ LangGraph 生态绑定      │
  │ Langfuse     │ 被 ClickHouse  │ 最强开源选项            │
  │              │ 收购 ($15B D轮) │                        │
  │ Helicone     │ 被 Mintlify    │ 成本监控，仍可自托管    │
  │              │ 收购           │                        │
  │ Arize        │ 企业级         │ Drift 检测，合规行业    │
  └──────────────┴────────────────┴────────────────────────┘

  ─────────────────────────────────────────────────────────
  真实接入示例（Langfuse）:

  # from langfuse.decorators import observe
  # @observe(name="agent_run")
  # def run_agent(task):
  #     response = litellm.completion(...)
  #     ...
  # 所有调用自动上报到 Langfuse Dashboard
""")

    provider.shutdown()


if __name__ == "__main__":
    main()
