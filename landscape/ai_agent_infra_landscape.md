# AI Agent 基础设施全景报告：沙箱、云电脑与 Agent Infra

> 调研日期：2026-06-16
> 覆盖范围：全球 + 中国市场，开源项目 + 商业公司

---

## 目录

1. [行业全景图](#一行业全景图)
2. [Agent 沙箱 / 代码执行](#二agent-沙箱--代码执行)
3. [云浏览器基础设施与 Browser Use](#三云浏览器基础设施与-browser-use)
4. [云电脑基础设施与 Computer Use 能力](#四云电脑基础设施与-computer-use-能力)
5. [编排、运行时与沙箱：三层拆解](#五编排运行时与沙箱三层拆解)
6. [Agent 协议层](#六agent-协议层)
7. [Agent 可观测性](#七agent-可观测性)
8. [Agent 安全 / 网关 / Auth](#八agent-安全--网关--auth)
9. [关键收购与信号](#九关键收购与信号)
10. [中国市场专题](#十中国市场专题)
11. [选型指南](#十一选型指南)
12. [产品架构拆解](#十二产品架构拆解)

---

## 一、行业全景图

```
                    AI Agent 基础设施栈 (2026)
┌─────────────────────────────────────────────────────────────┐
│                    应用层 / Agent Products                    │
│  Devin · Manus · Claude Cowork · OpenAI Codex · Cursor      │
├─────────────────────────────────────────────────────────────┤
│                    编排层 / Orchestration                     │
│  LangGraph · CrewAI · AutoGen/AG2 · OpenAI Agents SDK · ADK │
├─────────────────────────────────────────────────────────────┤
│                    协议层 / Protocols                        │
│  MCP (Anthropic) · A2A (Google) · ACP (IBM) · ASL (蚂蚁)    │
├─────────────────────────────────────────────────────────────┤
│                    运行时 / Agent Runtime                    │
│  Local Python · AWS Lambda · 阿里云 FC · K8s Pod · Docker   │
├─────────────────────────────────────────────────────────────┤
│                    沙箱层 / Sandbox                          │
│  E2B · Daytona · Modal · Runloop · CubeSandbox · AgentBay   │
│                    云浏览器 / Cloud Browser                  │
│  Browserbase · Browserless · Steel · Notte                  │
├─────────────────────────────────────────────────────────────┤
│                    可观测性 / Observability                   │
│  Braintrust · LangSmith · Langfuse · Helicone · Arize       │
├─────────────────────────────────────────────────────────────┤
│                    安全层 / Auth & Gateway                   │
│  Arcade.dev · ShieldAgent · Okta Agent Gateway               │
├─────────────────────────────────────────────────────────────┤
│                    计算层 / Compute                          │
│  Firecracker microVM · gVisor · Kata · WASM · OCI Container │
│  Cloud Desktop (无影/Citrix/WorkSpaces) · GPU Cloud (Modal)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、Agent 沙箱 / 代码执行

### 全球头部项目

| 平台 | Stars | 融资 | 冷启动 | 隔离技术 | 关键特性 | 定价 |
|------|-------|------|--------|----------|----------|------|
| **E2B** | 12.6k | $21M A轮 | ~150ms | Firecracker microVM | SDK 成事实标准，OpenAI/Claude 生态集成 | 按秒，Free/$150/mo |
| **Daytona** | 72.4k | ~$5M 种子轮 | **<90ms** | OCI + 独立内核 | LSP/Git/Snapshot，OpenAI SDK Provider | 按秒，$0.05/vCPU/h |
| **Modal** | — | >$100M ARR | 快 | 容器 | **GPU 原生**，适合推理+执行一体 | 按秒，按量 |
| **Runloop** | ~31 | 未公开 | 快 | microVM | Agent Gateway + Benchmark 评估 | $250/mo 起 |
| **Morph Cloud** | — | 早期 | — | 快照/Fork VM | Snapshot-and-Fork 原语 | 未公开 |
| **Ona (原 Gitpod)** | — | **被 OpenAI 收购** | — | 持久化沙箱 | Codex 持久化 Agent 沙箱 | OpenAI 内部 |
| **SmolVM** | 594 | 无 | 毫秒级 | Firecracker | 一次性 Agent VM，预装 Claude/Codex CLI | 开源免费 |
| **Qovery** | — | 商业 | — | 全栈克隆 | **克隆生产环境**（App+DB+服务+种子数据） | 企业级 |

### 超级玩家入场

| 玩家 | 项目 | 时间 | 意义 |
|------|------|------|------|
| **NVIDIA** | OpenShell | GTC 2026 | 策略驱动的 Agent 沙箱运行时，开源 |
| **Google** | GKE Agent Sandbox + Agent Substrate | 2026.6 GA | 超级云厂商入场，开源 Agent Substrate |
| **OpenAI** | 收购 Ona (Gitpod) | 2026.6.11 | 给 Codex 配持久化沙箱 |

### 中国沙箱玩家

| 平台 | Stars | 厂商 | 冷启动 | 隔离技术 | 关键差异 |
|------|-------|------|--------|----------|----------|
| **腾讯 CubeSandbox** | 4,000+ (4天) | 腾讯云 | **<60ms** | RustVMM+KVM | **E2B 原生兼容**，单机 2000+ 实例，内存<5MB/实例 |
| **OpenSandbox** | 11.5k | 阿里云 | 预热极快 | MicroVM+K8s | 5 种 SDK，E2B 兼容，K8s 原生 |
| **AgentBay** | 1.1k | 阿里云无影 | ~1.8s (实测) | 云电脑 VM | **唯一 Mobile Use**，88 个 MCP 工具 |
| **AgentRun** | — | 阿里云 FC | ~5s / 1ms唤醒 | FC microVM | Agent 全栈平台，非纯沙箱 |
| **SandboxFusion** | — | 字节跳动 | — | namespace+cgroup | 23 种语言，定位代码评测 |
| **AIO Sandbox** | — | 字节 Web Infra | — | 容器 | 浏览器+代码+终端一体化 |
| **AgentCube** | — | 华为 Volcano | 毫秒级 | K8s + gVisor | Warm Pool 预热，K8s 一等公民 |
| **AgentSphere** | — | 华为云 | 100ms | — | 每分钟十万级批创 |
| **PPIO** | — | 创业公司 | — | — | 兼容 E2B，分布式 GPU+沙箱一体 |
| **七牛云** | — | 七牛 | 200ms | Firecracker | 按秒计费 |

> **趋势：E2B SDK 接口成为事实标准。** 腾讯 CubeSandbox、阿里 ACS、PPIO 均原生兼容 E2B 接口，形成"国内替代路径"。

---

## 三、云浏览器基础设施与 Browser Use

> **概念区分：** 云浏览器 = 基础设施（提供 Chromium 实例），Browser Use = AI 能力/框架（AI 自主操控浏览器）。  
> 类比：云浏览器是"车"，Browser Use 是"会开车的 AI 司机"。

### 3.1 云浏览器 = 基础设施

提供远程 Chromium 实例池，Agent 通过 CDP/Playwright 协议连接。

| 平台 | 类型 | 特色 | 开源 |
|------|------|------|------|
| **Browserbase** | 托管云 Chromium | Stagehand SDK (Playwright 兼容)，反检测+验证码处理 | SDK 开源 |
| **Browserless** | 托管无头浏览器 API | 20+ 方法合并为 1 个 MCP 工具，Token 最省 | SaaS |
| **Steel** | 云浏览器 API | 为 AI Agent 优化的浏览器池 | — |
| **Notte** | AI 浏览器 | 专为 Agent 设计的浏览器接口 | — |

### 3.2 Browser Use = AI 能力/框架

AI 框架，让 LLM 自主操控浏览器完成任务（搜索、填表、下单等）。Browser Use 框架**消费**云浏览器基础设施。

| 框架 | Stars | 特色 | 与云浏览器的关系 |
|------|-------|------|-----------------|
| **Browser Use** | 25k | 支持任意 LLM，1000+ 社区插件，MIT 开源 | 可连接 Browserbase/本地 Chromium |
| **Stagehand** | — | Browserbase 官方 SDK，Playwright 兼容 | Browserbase 原生客户端 |
| **Scrapybara** | — | Desktop+Browser 混合沙箱 | 自带浏览器 + 桌面环境 |

### 3.3 关系说明

```
  Browser Use (AI 框架)          云浏览器 (基础设施)
  ┌──────────────────┐          ┌──────────────────┐
  │ LLM 驱动的决策    │          │ 远程 Chromium 池  │
  │ "点击登录按钮"    │ ──CDP──→ │ 反检测、验证码     │
  │ "填写搜索框"      │          │ 截图、DOM 访问    │
  └──────────────────┘          └──────────────────┘
  消费方                         提供方

  Agent 也可以不用 Browser Use 框架，直接用 Playwright 连接云浏览器。
  Browser Use 的价值是：让 LLM 自主决定"看哪里、点哪里"，而非写死脚本。
```

---

## 四、云电脑基础设施与 Computer Use 能力

> **概念区分：** 云电脑 = 基础设施（提供远程桌面 VM），Computer Use = AI 能力（AI 通过截图+鼠标控制桌面）。  
> 类比：云电脑是"一台远程的电脑"，Computer Use 是"AI 会操作这台电脑"。

### 4.1 云电脑 = 基础设施

提供远程桌面虚拟机（Linux/Windows/Android），Agent 可以通过 VNC/RDP 连接。

| 平台 | 传统定位 | AI 转型动作 |
|------|----------|------------|
| **阿里云无影** | 企业云桌面 | **AgentBay**：Agent 云基础设施，Linux/Windows/Android 沙箱 |
| **Citrix** | 企业 VDI | 未明确转型 Agent |
| **VMware Horizon** | 企业 VDI | 被 Broadcom 收购后收缩 |
| **Amazon WorkSpaces** | 托管桌面 | 未明确 Agent 定位 |
| **Computer Agents** | 新创 | 每个 Agent 一台持久化云电脑，$20/月 |

### 4.2 Computer Use = AI 能力

AI 模型通过截屏 + 鼠标/键盘操控来使用电脑，是一种**模型能力**而非基础设施。

| 厂商 | 产品 | 状态 | 实现方式 |
|------|------|------|---------|
| **Anthropic** | Claude Computer Use → Claude Cowork | 活跃 | 屏幕截图 + 坐标点击，Agent SDK 封装 |
| **OpenAI** | Operator / CUA | 2025.8 退役 | CUA 模型仍可通过 API 访问 |
| **Google** | Project Mariner | 集成 Gemini | 浏览器控制 Agent |
| **Manus** | 通用 Computer Agent | 活跃 | 中国团队，2025 年初爆红 |

### 4.3 两者的关系

```
  Computer Use (AI 能力)         云电脑 (基础设施)
  ┌──────────────────┐          ┌──────────────────┐
  │ Claude/GPT 模型   │          │ 远程 Ubuntu VM   │
  │ "看到了登录按钮"   │ ←截图── │ VNC/RDP 连接     │
  │ "点击 (x=320,     │ ──操控→ │ 4C/7G/99G 资源   │
  │  y=450)"          │          │ 完整 GUI 桌面    │
  └──────────────────┘          └──────────────────┘
  需要模型具备视觉理解            需要计算资源

  Computer Use 需要云电脑作为执行基底。
  但云电脑不一定用于 Computer Use —— 也可以只跑命令行。
  
  AgentBay 是两者结合的典型：
  - 云电脑基础设施：提供 Linux/Windows/Android VM
  - Computer Use 能力：提供截屏、点击等 MCP 工具
```

> **结论：** 传统 VDI 厂商尚未集体转向 Agent 基础设施。阿里云无影是全球唯一将云电脑产品明确转型为 Agent Infra 的厂商。

### 全栈 Agent 计算平台（Coding Agent）

| 平台 | 融资/估值 | 架构 |
|------|----------|------|
| **Devin (Cognition)** | $131M C轮 ($1.5B)，后达 $4.5B | 沙箱 VM（Shell+Browser+Editor），多 VM 并行 |
| **Cursor** | — | 本地 + 云端混合 |
| **Windsurf** | 被 Cognition (Devin) 收购 | — |

---

## 五、编排、运行时与沙箱：三层拆解

> **这是最容易混淆的三个概念。** 本章严格区分它们。

### 5.1 编排层 (Orchestration) — Agent "决定做什么"

编排层是 Agent 的"大脑"，负责：接收任务 → 推理 → 选择工具 → 调用工具 → 观察结果 → 重复。

| 框架 | Stars | 维护方 | 最适合 | 关键特性 |
|------|-------|--------|--------|----------|
| **LangGraph** | ~40k (LangChain 生态) | LangChain ($30M+ A轮) | **生产级有状态 Agent** | 图工作流、检查点、Human-in-the-loop |
| **CrewAI** | ~25k | 开源社区 | 多 Agent 快速原型 | 角色定义、团队协作范式 |
| **AutoGen / AG2** | — | 独立社区 (原 MS) | 研究级多 Agent 对话 | 对话式多 Agent，重构为 AG2 |
| **OpenAI Agents SDK** | — | OpenAI | 极简 Agent 开发 | 原生沙箱 Provider 集成（E2B/Daytona/Modal/Runloop） |
| **Google ADK** | — | Google | Gemini + Vertex 深度集成 | Google 全家桶 |
| **AgentScope** | — | 阿里通义 | 企业级多 Agent 协作 | ReAct、分布式 Actor、沙箱隔离执行 |
| **Dify** | 140k | 国产团队 | 可视化 Agent 应用开发 | 工作流+RAG，Docker 一键部署 |
| **Coze** | — | 字节跳动 | 低门槛 Bot 搭建 | 模板化、插件生态丰富 |

### 5.2 运行时 (Runtime) — Agent "自己的代码跑在哪里"

运行时是 Agent 进程本身运行的计算环境。这是**你自己的代码**（可信的），不是 LLM 生成的代码。

| 运行时类型 | 典型场景 | 特点 |
|-----------|---------|------|
| **本地 Python 进程** | 开发调试：`python agent.py` | 零开销，无隔离，开发用 |
| **云函数 (Serverless)** | AWS Lambda、阿里云 FC | 按量计费，自动扩缩，无状态 |
| **K8s Pod** | 企业部署 | 可编排，可持久化，适合长运行 Agent |
| **Docker 容器** | 自托管部署 | 轻量隔离，CI/CD 友好 |
| **Ona (Gitpod) VM** | OpenAI Codex | 持久化 VM，Agent 运行在沙箱内部 |

> **关键区分：** Runtime 托管的是**你写的 Agent 代码**（编排逻辑、API 调用、状态管理）。  
> Sandbox 托管的是 **LLM 生成的代码**（不可信，需要隔离执行）。

### 5.3 沙箱 (Sandbox) — Agent "在哪里执行不可信操作"

沙箱是 Agent 工具调用的隔离执行环境。LLM 生成的代码完全不可信，必须在隔离的 VM/容器中执行。

详见第二章「Agent 沙箱 / 代码执行」的完整列表。

### 5.4 三层关系 — 以一次真实调用为例

```
  用户: "帮我分析这个 CSV 文件"
  
  ┌── 编排层 (Orchestration) ──────────────────────────────────┐
  │  LangGraph / OpenAI Agents SDK / 自研编排逻辑              │
  │                                                            │
  │  Step 1: LLM 推理 → "需要写 Python 代码用 pandas 分析"    │
  │  Step 2: LLM 生成代码 → "import pandas as pd; ..."       │
  │  Step 3: 调用工具 → tool_call: execute_code(code=...)     │
  │  Step 4: 收到结果 → LLM 综合回答用户                      │
  └──────────────────────────┬─────────────────────────────────┘
                             │ 编排逻辑决定"调用沙箱执行代码"
  ┌── 运行时 (Runtime) ───────┴────────────────────────────────┐
  │  Agent 进程跑在 AWS Lambda / K8s Pod / 本地                │
  │                                                            │
  │  agent.py 调用 e2b_sdk.sandbox.execute(code)              │
  │  这行代码是你写的，是可信的                                 │
  └──────────────────────────┬─────────────────────────────────┘
                             │ API 调用到沙箱服务
  ┌── 沙箱 (Sandbox) ────────┴────────────────────────────────┐
  │  E2B Firecracker microVM / AgentBay Cloud VM              │
  │                                                            │
  │  LLM 生成的 pandas 代码在这里执行                          │
  │  即使代码有 rm -rf / 也不会影响宿主                        │
  │  执行完毕，沙箱可以销毁                                    │
  └───────────────────────────────────────────────────────────┘
```

### 5.5 不同产品的三层组合方式

| 产品 | 编排层 | 运行时 | 沙箱 | 特点 |
|------|--------|--------|------|------|
| **Codex (OpenAI)** | OpenAI Agents SDK | Ona (Gitpod) VM | 同 Runtime (合并) | Runtime=Sandbox，Agent 跑在沙箱里 |
| **Claude Code** | Claude 模型推理 | 本地 CLI 进程 | 无独立沙箱 (或 E2B) | 用权限控制代替隔离 |
| **Devin** | 自研编排引擎 | 自建云 VM | 同 Runtime (合并) | 三层全自建，Shell+Browser+Editor |
| **LangGraph + E2B** | LangGraph | K8s Pod | E2B microVM | 三层分离，最灵活 |
| **AgentRun** | 内置编排 | 阿里云 FC | FC microVM | 平台级产品，三层打包 |

---

## 六、Agent 协议层

```
              Agent 协议栈 (2026)

  ┌──────────────────────────────────────┐
  │  A2A (Google)  Agent ⟷ Agent 通信    │
  ├──────────────────────────────────────┤
  │  MCP (Anthropic) Agent ⟷ Tool 集成   │  ← 采用最广
  ├──────────────────────────────────────┤
  │  ACP (IBM)    企业级 Agent 通信       │
  ├──────────────────────────────────────┤
  │  ASL (蚂蚁)   Agent 安全链路协议      │
  └──────────────────────────────────────┘
```

| 协议 | 发起方 | 定位 | 采用情况 |
|------|--------|------|----------|
| **MCP** | Anthropic | Agent ↔ 工具/数据源 | **最广泛**：AWS MCP Server GA，数千个 MCP Server 生态 |
| **A2A** | Google | Agent ↔ Agent 互操作 | 2025.4 发布，与 MCP 互补（MCP=工具，A2A=Agent间） |
| **ACP** | IBM | 企业级 Agent 通信 | 企业场景，开源牵引力弱于 MCP/A2A |
| **ASL** | 蚂蚁集团 | Agent 安全链路 | 2026.4 发布，聚焦跨 Agent 身份/意图/授权安全 |

---

## 七、Agent 可观测性

| 平台 | 融资/动态 | 类型 | 关键特性 |
|------|----------|------|----------|
| **Braintrust** | **$80M B轮** (2026.2, ~$800M 估值) | 评估优先 | 自动 Trace 每个 LLM/Tool 调用，Eval 驱动 |
| **LangSmith** | LangChain 内置 | 原生 Trace | LangGraph/LangChain 生态绑定 |
| **Langfuse** | **被 ClickHouse 收购** (2026.1, $15B 估值的 $400M D轮) | 开源 | 最强开源选项 |
| **Helicone** | **被 Mintlify 收购** (2025底) | 开源 | 成本监控+代理，仍可自托管 |
| **Arize AI** | 企业级 | 商业 | Telemetry + Drift 检测，适合合规行业 |

> **趋势：** 可观测性赛道快速整合，独立开源项目被收购（Langfuse → ClickHouse，Helicone → Mintlify），Braintrust 以高估值独立融资。

---

## 八、Agent 安全 / 网关 / Auth

| 平台 | 融资 | 定位 |
|------|------|------|
| **Arcade.dev** | **$60M A轮** (2026.6) | Agent "安全行动层"：管理 Auth、权限、工具授权 |
| **ShieldAgent** | — | MCP 防火墙，面向 EU AI Act 合规 (2026.8 截止) |
| **Okta Agent Gateway** | 上市公司 | 企业身份 → Agent 身份/Auth 扩展 |
| **蚂蚁 ASL** | — | Agent 安全链路协议：身份验证+意图防篡改+授权边界 |

---

## 九、关键收购与信号

### 2025-2026 重大事件

| 时间 | 事件 | 影响 |
|------|------|------|
| 2025.10 | E2B 完成 $21M A轮 | Agent 沙箱赛道被验证 |
| 2025底 | Helicone 被 Mintlify 收购 | 可观测性整合开始 |
| 2026.1 | Langfuse 被 ClickHouse 收购 ($15B D轮) | 开源可观测性被吸收 |
| 2026.2 | Braintrust $80M B轮 (~$800M 估值) | Agent 评估独立赛道成立 |
| 2026.3 | Devin 估值达 $4.5B | Coding Agent = 沙箱最大用户 |
| 2026.4 | 腾讯 CubeSandbox 开源 (4天 4k Star) | 中国最快开源沙箱 |
| 2026.6 | Arcade.dev $60M A轮 | Agent Auth 独立赛道 |
| 2026.6 | Google GKE Agent Sandbox GA | 超级云入场 |
| 2026.6 | NVIDIA OpenShell 开源 (GTC) | GPU 巨头入场沙箱 |
| **2026.6.11** | **OpenAI 收购 Ona (Gitpod)** | **沙箱成为 AI Lab 标配** |
| 2026.6.15 | 阿里 ACS Agent Sandbox 降价 | 中国价格战开始 |
| 2026.6 | 华为 AgentSphere 发布 | 每分钟十万级沙箱批创 |

### 宏观信号

- **Q1 2026**：1,800 家 AI Agent 创业公司关闭，但同季度融资 **$178B** → 基础设施 > 套壳应用
- **沙箱成 AI Lab 标配**：OpenAI 买了（Ona），Anthropic 合作（Daytona/E2B），Google 自建（GKE）
- **E2B SDK 接口成为行业标准**：腾讯 CubeSandbox、阿里 ACS、PPIO 均宣布兼容

---

## 十、中国市场专题

### 竞争格局

```
                    中国 Agent 基础设施竞争格局

     阿里云                    腾讯云              华为云
  ┌──────────┐           ┌───────────┐       ┌──────────┐
  │ 无影AgentBay│          │CubeSandbox│       │AgentCube │
  │ ACS Sandbox│          │  (E2B兼容) │       │AgentSphere│
  │ AgentRun   │          │           │       │          │
  │ OpenSandbox│          └───────────┘       └──────────┘
  └──────────┘
                    字节跳动                   蚂蚁集团
                ┌───────────┐            ┌──────────┐
                │SandboxFusion│           │ ASL 协议  │
                │AIO Sandbox │            │ 安全治理  │
                │ Coze 平台   │            └──────────┘
                └───────────┘
                              创业公司
                         ┌──────────────┐
                         │ PPIO (E2B兼容)│
                         │ 七牛云沙箱     │
                         │ 星舟无界       │
                         └──────────────┘
```

### 技术指标对比（中国玩家）

| 指标 | 腾讯 CubeSandbox | 阿里 ACS | 华为 AgentSphere | 阿里 AgentBay |
|------|-----------------|----------|-----------------|---------------|
| 冷启动 | **<60ms** | 快 (预热池) | 100ms | ~1.8s (完整VM) |
| 单机密度 | 2000+ 实例 | — | — | — |
| 批量创建 | — | 15,000/分 | **100,000/分** | — |
| 单实例内存 | <5MB | — | — | 7.1GB |
| E2B 兼容 | ✅ | ✅ | ❌ | ❌ |
| Mobile Use | ❌ | ❌ | ❌ | **✅** |
| K8s 原生 | ❌ | ✅ | ✅ | ❌ |
| 开源状态 | ✅ Apache 2.0 | ✅ | ✅ | SDK 开源 |

---

## 十一、选型指南

### 按场景选型

| 场景 | 全球首选 | 中国首选 | 理由 |
|------|---------|---------|------|
| **LLM 代码执行** | E2B | 腾讯 CubeSandbox | E2B 生态最好；CubeSandbox E2B 兼容+60ms启动 |
| **Coding Agent（clone+test）** | Daytona | AgentRun | Daytona 90ms+Git 原生；AgentRun FC 体系完整 |
| **Browser Use Agent** | Browserbase | AgentBay | Browserbase 反检测最强；AgentBay 有 VNC 可视化 |
| **Mobile Agent (App自动化)** | **无替代** | **AgentBay（唯一）** | 全球唯一支持 Android 沙箱的 Agent 平台 |
| **Computer Use (GUI)** | Claude Cowork | AgentBay | Anthropic 原生；AgentBay 提供完整云桌面 |
| **GPU + 执行一体化** | Modal | — | Modal 是唯一 GPU 原生沙箱 |
| **大规模 RL 训练** | — | 腾讯 CubeSandbox | 百亿级调用验证，高密度低内存 |
| **K8s 私有化部署** | GKE Agent Sandbox | OpenSandbox / AgentCube | Google 自建生态；阿里/华为 K8s 原生 |
| **生产环境克隆测试** | Qovery | — | 全栈克隆独家能力 |
| **Agent Auth / 权限** | Arcade.dev | — | $60M A轮，品类领导者 |
| **Agent 可观测性** | Braintrust / Langfuse | LangSmith | Braintrust 评估最强；Langfuse 开源最好 |

### 技术选型决策树

```
你的 Agent 需要什么？
│
├─ 执行代码 → 需要 GPU？
│   ├─ 是 → Modal
│   └─ 否 → 需要 E2B 兼容生态？
│       ├─ 是 → E2B (海外) / CubeSandbox (中国) / ACS (中国)
│       └─ 否 → 需要持久状态？
│           ├─ 是 → Daytona / AgentRun
│           └─ 否 → E2B / SmolVM (自托管)
│
├─ 操作浏览器 → 需要反检测？
│   ├─ 是 → Browserbase
│   └─ 否 → Browser Use (开源免费) / AgentBay
│
├─ 操作桌面 GUI → 操作移动端？
│   ├─ 是 → AgentBay（唯一选择）
│   └─ 否 → AgentBay / Claude Computer Use
│
├─ K8s 集群自托管 → OpenSandbox / AgentCube / GKE Agent Sandbox
│
└─ 全栈 Agent 平台 → AgentRun / Dify / Coze
```

---

## 十二、产品架构拆解

用三个真实产品说明编排、运行时、沙箱如何组合。

### OpenAI Codex

```
  用户在 ChatGPT 里说："Fix the failing test in my repo"
  
  ┌── ① 编排层 ──────────────────────────────────────────────┐
  │  OpenAI Agents SDK + 内部编排逻辑                         │
  │  解析意图 → 规划步骤 → 选择工具 → 管理多轮状态            │
  └──────────────────────────┬───────────────────────────────┘
                             ↓
  ┌── ② 运行时 + ③ 沙箱 (合并) ──────────────────────────────┐
  │  Ona (原 Gitpod，2026.6 被 OpenAI 收购)                   │
  │  - Agent 进程本身跑在 Ona VM 里                           │
  │  - git clone、npm install、pytest 都在同一 VM 执行        │
  │  - 持久化：关掉浏览器，代码还在                           │
  └───────────────────────────────────────────────────────────┘
  
  关键设计：Runtime = Sandbox (Agent 跑在自己的沙箱里)
  优点：低延迟（无跨进程 API 调用）
  代价：OpenAI 花钱收购 Ona 来解决持久化沙箱问题
```

### Claude Code (你正在使用的)

```
  你在终端说："帮我修这个 bug"
  
  ┌── ① 编排层 ──────────────────────────────────────────────┐
  │  Claude 模型推理 + 工具调用框架                            │
  │  系统 prompt 定义行为 → 多步推理 → 权限控制                │
  └──────────────────────────┬───────────────────────────────┘
                             ↓
  ┌── ② 运行时 ──────────────────────────────────────────────┐
  │  Claude Code CLI 进程 (Node.js)                           │
  │  跑在你的本地机器 / 或 OpenSandbox 环境                    │
  │  管理与 Anthropic API 的通信、工具执行                     │
  └──────────────────────────┬───────────────────────────────┘
                             ↓
  ┌── ③ 沙箱 ───────────────────────────────────────────────┐
  │  【本地模式】无独立沙箱 — 直接操作你的真实文件系统          │
  │    → 用权限提示 ("是否允许执行?") 代替隔离                 │
  │  【你当前的环境】OpenSandbox VM — 所有操作被限制在 VM 内   │
  └───────────────────────────────────────────────────────────┘
  
  关键设计：Runtime ≠ Sandbox (分离或无沙箱)
  优点：灵活，可接入 E2B/Daytona 作为远程沙箱
  代价：本地模式无隔离，依赖信任和权限控制
```

### Devin (Cognition, $4.5B)

```
  用户提交任务："Implement dark mode for the app"
  
  ┌── ① 编排层 ──────────────────────────────────────────────┐
  │  自研多 Agent 编排引擎                                    │
  │  任务分解 → 并行规划 → 工具编排 → 自动重试                │
  └──────────────────────────┬───────────────────────────────┘
                             ↓
  ┌── ② 运行时 + ③ 沙箱 (合并) ──────────────────────────────┐
  │  每个任务一台独立 VM                                      │
  │  ├── Shell (命令行操作)                                   │
  │  ├── Browser (Chromium，可上网搜 StackOverflow)           │
  │  └── Editor (VS Code 风格，实时展示改动)                  │
  │  可同时开多台 VM 并行处理不同任务                          │
  └───────────────────────────────────────────────────────────┘
  
  关键设计：三层全自建，Shell+Browser+Editor 三合一
  优点：完全控制，用户体验最好
  代价：最重，估值 $4.5B 对应的就是这套自建基础设施
```

### 对比总结

| 维度 | Codex | Claude Code | Devin |
|------|-------|-------------|-------|
| Runtime 与 Sandbox | 合并 | 分离 | 合并 |
| 沙箱来源 | 收购 (Ona) | 无 / 外部 (E2B) | 自建 |
| 持久化 | ✅ | ❌ (依赖本地) | ✅ |
| Browser 内置 | ❌ | ❌ | ✅ |
| 成本 | 高 (收购) | 低 (无沙箱) | 最高 (全自建) |
| 用户体验 | 中 | 灵活 | 最好 |

---

## 附录：值得关注的 GitHub 项目

| 项目 | Stars | 链接 | 一句话 |
|------|-------|------|--------|
| Daytona | 72.4k | github.com/daytonaio/daytona | 最快冷启动的 Agent 沙箱 |
| Dify | 140k | github.com/langgenius/dify | 可视化 Agent 应用平台 |
| Browser Use | 25k | github.com/browser-use/browser-use | 开源浏览器自动化框架 |
| E2B | 12.6k | github.com/e2b-dev/E2B | Agent 沙箱事实标准 |
| OpenSandbox | 11.5k | github.com/alibaba/OpenSandbox | 阿里开源全栈沙箱 |
| CubeSandbox | 4k+ | github.com/anthropics/... (腾讯) | E2B 兼容，60ms 启动 |
| CrewAI | 25k | github.com/crewAIInc/crewAI | 多 Agent 团队框架 |
| AgentBay SDK | 1.1k | github.com/aliyun/wuying-agentbay-sdk | 云电脑 Agent SDK |
| SmolVM | 594 | github.com/celestoai/smolvm | Firecracker 一次性 Agent VM |
| SandboxFusion | — | github.com/bytedance/SandboxFusion | 23 语言代码评测沙箱 |

---

*数据来源：GitHub、Crunchbase、公开融资公告、官方文档、技术博客*
*报告持续更新中，最新版本见 GitHub repo*
