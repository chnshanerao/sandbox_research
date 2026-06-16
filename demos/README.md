# AI Agent 基础设施 — 分层 Demo

每个 Demo 对应 Agent 基础设施栈的一个层次，可独立运行。

```
                    AI Agent 基础设施栈
┌─────────────────────────────────────────────────────────┐
│  编排层 / Orchestration       → Demo 02                  │
├─────────────────────────────────────────────────────────┤
│  协议层 / Protocols (MCP)     → Demo 03                  │
├─────────────────────────────────────────────────────────┤
│  沙箱层 / Sandbox             → Demo 01a (AgentBay)      │
├─────────────────────────────────────────────────────────┤
│  可观测性 / Observability     → Demo 04                  │
├─────────────────────────────────────────────────────────┤
│  安全层 / Auth & Gateway      → Demo 05                  │
├─────────────────────────────────────────────────────────┤
│  计算层 / Compute             → Demo 01b (Docker)        │
├─────────────────────────────────────────────────────────┤
│  全栈组合 / E2E Agent         → Demo 07                  │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 激活环境
source /tmp/sandbox-bench/bin/activate

# 设置 AgentBay API Key (Demo 01a 和 07 需要)
export AGENTBAY_API_KEY="akm-3d21e663-3224-4cee-ae77-a6c6c7ccb6d7"
```

## Demo 列表

| Demo | 对应层 | 运行命令 | 需要 API Key | 耗时 |
|------|--------|---------|-------------|------|
| **01a: AgentBay 沙箱** | 沙箱层 | `python3 demos/01_sandbox/demo_agentbay_sandbox.py` | AgentBay | ~5s |
| **01b: Docker 隔离** | 计算层 | `python3 demos/01_sandbox/demo_docker_isolation.py` | 无 | ~20s |
| **02: 编排循环** | 编排层 | `python3 demos/02_orchestration/demo_orchestration_loop.py` | 无 | <1s |
| **03: MCP 协议** | 协议层 | `python3 demos/03_mcp_protocol/mcp_client.py` | 无 | ~2s |
| **04: 可观测性** | 可观测性 | `python3 demos/04_observability/demo_observability.py` | 无 | <1s |
| **05: 安全授权** | 安全层 | `python3 demos/05_auth/demo_auth_patterns.py` | 无 | <1s |
| **07: 全栈 Agent** | 全栈组合 | `python3 demos/07_agent_e2e/demo_agent_e2e.py` | AgentBay | ~5s |

## 各 Demo 说明

### Demo 01a: AgentBay 云端沙箱
演示沙箱生命周期：创建 → Shell/Python/文件操作 → VNC 可视化 → 销毁。
展示 Agent 为何需要隔离执行环境。

### Demo 01b: Docker 容器隔离
本地 Docker 容器隔离：PID/文件系统命名空间、资源限制、网络隔离。
对比 Docker/gVisor/Firecracker/VM/WASM 五种隔离技术。

### Demo 02: ReAct 编排循环
Agent 编排核心：Think → Tool Call → Observe → Repeat。
使用 MockLLM（LLM API 不可用时），保留真实 LLM 代码注释。

### Demo 03: MCP 协议
MCP Server 暴露 3 个工具，MCP Client 通过 stdio 连接并调用。
展示 Agent 协议层的工具发现和调用机制。

### Demo 04: 可观测性
OpenTelemetry 追踪 Agent 调用链：agent.run → llm.call → tool.call。
自定义属性记录模型、Token 用量、工具耗时。

### Demo 05: 安全授权
API Key 管理 + 工具白/黑名单 + 路径校验 + 速率限制 + 审计日志。
展示 Agent 安全网关的拦截机制。

### Demo 07: 全栈 Agent
将编排 + 安全 + 沙箱 + 追踪四层组合，在 AgentBay VM 中执行多步任务。
完整演示 Agent 基础设施栈的协作方式。

## 依赖

```
wuying-agentbay-sdk  (已装)
openai               (已装)
mcp                  (需安装: pip install mcp)
opentelemetry-api    (需安装: pip install opentelemetry-api opentelemetry-sdk)
```
