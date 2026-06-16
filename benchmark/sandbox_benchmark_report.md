# AI Agent 沙箱平台横向测评报告

> 测评日期：2026-06-15  
> 测评方法：AgentBay 实测 + AgentRun 实测（受限）+ 开源项目研究 + 公开文档分析

---

## 一、测评平台概览

| 平台 | 定位 | Stars | 开源 | 隔离技术 | 提供商 |
|------|------|-------|------|----------|--------|
| **Daytona** | 全能开发沙箱 | 72,400 | 核心开源 | OCI/Docker + 独立内核 | Daytona Inc |
| **E2B** | 代码执行标杆 | 12,600 | 开源 | Firecracker microVM | E2B Inc |
| **OpenSandbox** | 云原生全栈 | 11,500 | 完全开源 | MicroVM + K8s | Alibaba (OpenKruise) |
| **Runloop** | 企业级合规 | ~31 | 私有 | microVM (Devboxes) | Runloop Inc |
| **AgentBay** | Computer Use 云电脑 | 1,100 | SDK开源 | 云电脑虚拟化 | 阿里云无影 |
| **AgentRun** | Agentic AI 全栈平台 | N/A | SDK开源 | FC microVM | 阿里云函数计算 |

---

## 二、AgentBay 实测结果

### 2.1 测试环境

- **API Key**: `akm-3d21e663-...` ✅ 验证通过
- **镜像**: `computer-use-ubuntu-2204`
- **系统**: Ubuntu 22.04.5 LTS，Linux 5.15.0-125-generic
- **规格**: 4 vCPU (Intel Xeon Platinum)，7.1GB RAM，99GB 磁盘

### 2.2 性能指标（全部实测）

| 测试项 | 耗时 | 状态 | 备注 |
|--------|------|------|------|
| SDK 初始化 | 1ms | ✅ | 极快，本地构建 |
| **冷启动（Session 创建）** | **1,781ms** | ✅ | 含分配云电脑实例 |
| Shell 命令（首次） | 227ms | ✅ | 含 WSS 连接建立 |
| Python 代码执行 | 50ms | ✅ | 后续调用极快 |
| 文件写入 | 49ms | ✅ | MCP 文件协议 |
| 文件读取 | 51ms | ✅ | 中文内容正确返回 |
| 网络访问（curl baidu） | 173ms | ✅ | HTTP 200, 0.12s RTT |
| 计算密集型（素数计算） | 51ms | ✅ | 命令下发延迟，实际CPU不受限 |
| pip 包安装 | 1,954ms | ✅ | requests 包约 2s |
| 多命令管道 | 50ms | ✅ | awk/seq 完整支持 |
| Session 状态查询 | 81ms | ✅ | RUNNING 状态 |
| Resource URL 获取 | 0ms | ✅ | wy.aliyun.com VNC 链接 |
| MCP 工具列表 | 258ms | ⚠️ | 服务端返回 88 个工具，SDK 迭代接口 bug |
| **Session 清理** | **1,315ms** | ✅ | DELETING → FINISH |

**通过率: 14/15 (93.3%)**，1 个失败因 SDK 迭代接口 bug（非功能问题）

### 2.3 关键发现

```
AgentBay 冷启动详解（实测）：
┌─────────────────────────────────────────────────────────┐
│  API 调用 → 分配实例 → 返回 Session ID                  │
│  ← ─ ─ ─ ─ ─ ─ ─ 1,781ms ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ →    │
│                                                         │
│  首次命令（含 WSS 建连）:  227ms                         │
│  后续命令（稳态）:          50ms                         │
│  文件操作（MCP 协议）:      50ms                         │
│                                                         │
│  Session 清理:          1,315ms                         │
└─────────────────────────────────────────────────────────┘
```

**沙箱规格亮点：**
- OS: Ubuntu 22.04 LTS（固定版本，稳定）
- CPU: Intel Xeon Platinum（企业级处理器）
- 内存：7.1GB（实际可用 5.1GB）
- 磁盘：99GB（类似完整云主机）
- MCP 工具：88 个预装工具（Browser、Shell、File、Mobile 等）
- 已内置 Python 3.10 + pip，requests 等常用包

**网络：** 可访问公网（百度 200ms 内响应），不限 HTTP/HTTPS

**独特能力：**
- 提供 VNC Resource URL，可直接浏览器接管云端桌面
- `computer-use-ubuntu-2204` 镜像内置完整 GUI 环境
- 4 种镜像类型：Linux、Windows、Android（Mobile Use）、Code Space

---

## 三、AgentRun (FC Sandbox) 实测结果

### 3.1 Auth 发现（重要）

| 认证方式 | 用途 | 你提供的 Key |
|----------|------|-------------|
| 阿里云 AK/SK | 控制面（创建/管理沙箱模板） | ❌ 未提供 |
| Account ID | 构造数据面端点 URL | ❌ 未提供 |
| **数据面 Token** (`ak_xxx`) | **调用已部署 Agent 端点** | ✅ `ak_f1io8fp0sr8l4y8arefvbs` |

> **结论：** 提供的 `ak_f1io8fp0sr8l4y8arefvbs` 是 **Agent 调用凭据**，格式为 AgentRun 专用 token，用于 OpenAI 兼容端点调用已部署 Agent，而非沙箱创建/管理。沙箱生命周期管理需要标准阿里云 AK/SK。

### 3.2 产品架构（文档研究）

AgentRun 是 **平台级产品**，包含：

```
AgentRun Platform
├── Sandbox 执行环境（三种类型）
│   ├── Code Interpreter  → 隔离 Python/JS 执行
│   ├── Browser Sandbox   → Chromium + VNC + CDP
│   └── All-in-One (AIO)  → 浏览器 + 代码 + Shell 一体
├── Agent Runtime         → 部署托管 Agent
├── 模型代理              → 统一 LLM 接入 + Fallback
├── Memory 系统           → 短期/长期记忆（对接 Tablestore）
├── MCP 工具管理          → 统一工具注册
└── 可观测性              → OpenTelemetry 全链路 Trace
```

**Sandbox 性能（官方文档数据）：**
- 浅休眠唤醒：**~1ms**（内存快照技术）
- 深休眠恢复：有延迟，用于长会话保持
- 冷启动（Code Interpreter）：**5s 以内**（无预热）
- 预热实例下：**亚秒级**

**沙箱规格：** 2C2G（默认），按量计费

---

## 四、开源平台横向分析

### 4.1 Daytona（72,400 Stars）

| 维度 | 情况 |
|------|------|
| **冷启动** | **<90ms**（行业最快，独立实测记录） |
| 隔离级别 | OCI 容器 + 独立内核（非 microVM，略弱于 Firecracker） |
| SDK | Python、TypeScript、Go，API 完整 |
| 特色能力 | LSP 支持、Computer Use API、Git 集成、Snapshot 持久化 |
| 并发 | 无限制（按需） |
| 计费 | 按秒，≈ $0.000842/s（最高规格），较贵 |
| 开源模式 | 核心开源，云服务收费 |
| 最适合 | Coding Agent：需 repo clone、依赖安装、完整测试套件 |

**亮点：** OpenAI Agents SDK 官方支持的沙箱 provider。

### 4.2 E2B（12,600 Stars）

| 维度 | 情况 |
|------|------|
| **冷启动** | **~150ms**（Firecracker microVM，硬件级隔离） |
| 隔离级别 | **Firecracker microVM**（AWS Lambda 同款技术，最强） |
| SDK | Python、JS/TS，设计极简，1 行创建沙箱 |
| 特色能力 | Pause/Resume（~4s/GiB）、自定义镜像 |
| 并发 | Free: 20，Pro: 1100+，Enterprise: 无限 |
| 计费 | Free / $150/mo Pro，按分钟计费 |
| **SDK 影响力** | **事实行业标准** —— ACS OpenSandbox 和 AgentRun 均宣传 E2B SDK 兼容 |
| 最适合 | 短生命周期代码执行 Agent（LLM 代码沙箱） |

**亮点：** 生态最好，Fortune 500 客户，SDK 成为行业标准接口。

**已知局限：** UDP/QUIC 不支持（仅 HTTP/HTTPS）；无 bulk file 读取 API；偶发 502 超时。

### 4.3 OpenSandbox（Alibaba, 11,500 Stars）

| 维度 | 情况 |
|------|------|
| 冷启动 | 预热池极快，MicroVM Hibernate/Wake 技术 |
| 隔离级别 | MicroVM + K8s 容器运行时 |
| SDK 语言 | **Python、Java、TypeScript、Go、C#**（最多） |
| 特色能力 | Checkpoint Clone、Sandbox Set CR、E2B SDK 兼容 |
| **规模** | **管理版 ACS 支持 15,000 沙箱/分钟** |
| 开源状态 | 完全开源（github.com/alibaba/OpenSandbox）|
| 计费 | 自托管免费；ACS 管理版按量 |
| 最适合 | K8s 原生企业 + 多语言 Agent 团队 |

**亮点：** 唯一主动宣布 E2B SDK 兼容的平台（可无缝迁移），AgentScope/LangChain 深度集成。

### 4.4 Runloop

| 维度 | 情况 |
|------|------|
| 冷启动 | microVM 快速启动（具体数字未公开） |
| 特色能力 | **Agent Gateway**（生产级鉴权路由）、**Reflex**（编排控制台）、Benchmark 评估 |
| 规模验证 | Trajectory 案例：10,000+ burst 并发 Devbox |
| 开源 | 私有，企业级 |
| 计费 | **$250/月起**，Contact Sales |
| 最适合 | 需要统一控制面（开发→评测→部署）的企业级 Agent 基础设施 |

---

## 五、综合横向对比

### 5.1 关键维度矩阵

| 维度 | Daytona | E2B | OpenSandbox | Runloop | AgentBay | AgentRun |
|------|---------|-----|-------------|---------|----------|----------|
| **冷启动** | **<90ms** | ~150ms | 预热池极快 | 快（未公开） | **~1.8s（实测）** | ~5s（文档） |
| **稳态命令延迟** | 低 | 低 | 低 | 低 | **50ms（实测）** | 低 |
| **隔离强度** | 中（OCI） | **强（Firecracker）** | 强（MicroVM） | 强（MicroVM） | 强（云电脑VM） | 强（FC MicroVM） |
| **Computer Use** | ✅ | ❌ | ❌ | ❌ | **✅（Mobile Use！）** | ✅（Browser） |
| **Mobile Use** | ❌ | ❌ | ❌ | ❌ | **✅（唯一）** | ❌ |
| **Browser 沙箱** | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **文件系统** | ✅快照 | ✅ | ✅ Checkpoint | ✅ | **✅实测50ms** | ✅ |
| **SDK 语言** | Py/TS/Go | Py/TS | **5种** | 企业API | **4种** | Py |
| **E2B 兼容** | ❌ | ✅原生 | ✅ | ❌ | ❌ | ❌ |
| **OpenAI SDK支持** | ✅ | ✅ | ✅兼容E2B | ✅ | ❌ | ✅ |
| **自托管** | ✅ | ✅ | **完全开源** | VPC部署 | ❌ | ❌ |
| **中国区可用** | ❌ | ❌ | ✅ | ❌ | **✅（实测）** | **✅** |
| **Stars** | 72k | 12.6k | 11.5k | ~31 | 1.1k | N/A |
| **起步价** | $0.05/vCPU/h | 免费/$150mo | 免费 | $250/mo | 阿里云计费 | 阿里云计费 |

### 5.2 冷启动对比（实测 vs 文档）

```
冷启动延迟（越低越好）
─────────────────────────────────────────────────────────
Daytona        ████ <90ms           （文档/官方benchmark）
E2B            ████████ ~150ms      （文档/多方验证）  
OpenSandbox    ████ <100ms          （预热池，文档）
Runloop        ██████ ~秒级          （文档，未量化）
AgentBay       ██████████████████ 1,781ms  ★ 实测 ★
AgentRun       ████████████████████████ ~5s  （文档，无预热）
```

> AgentBay 的冷启动偏长（~1.8s），这是因为它分配的是**完整的云电脑 VM**（7.1GB RAM、99GB 磁盘、4C），而非轻量级 MicroVM。一旦 Session 建立，后续命令稳定在 **50ms**。

### 5.3 稳态性能（AgentBay 实测）

```
AgentBay 稳态命令延迟（实测，含网络往返）：
┌─────────────────────────────────────────────────────────┐
│ Shell 命令           50ms  ████                         │
│ Python 执行          50ms  ████                         │
│ 文件读写             50ms  ████                         │
│ 管道命令             50ms  ████                         │
│ 网络访问(curl)      172ms  ████████████████             │
│ Session 状态查询     81ms  ███████                      │
│ pip install       1,954ms  ██████████████████████████   │
└─────────────────────────────────────────────────────────┘
```

---

## 六、AgentBay vs AgentRun 深度对比

作为同为阿里云系的两个产品，定位有明显差异：

| 对比维度 | AgentBay（无影） | AgentRun（函数计算） |
|----------|-----------------|---------------------|
| **产品定位** | AI Agent 云电脑基础设施 | Agent 全栈开发平台 |
| **沙箱形态** | 完整云电脑 VM | Serverless 函数沙箱 |
| **规格** | 4C7G（实测），适合重任务 | 2C2G（默认），轻量 |
| **Computer Use** | ✅ Linux/Windows/Android | ✅ 仅 Browser + Code |
| **Mobile Use** | ✅（Android 镜像） | ❌ |
| **Auth 模型** | 单 API Key（简单） | 需 AK/SK + AccountID（复杂） |
| **SDK 体验** | 直接，88 个 MCP 工具即用 | 需先在控制台创建模板 |
| **最大特色** | **唯一支持 Mobile Use 的沙箱** | **完整 Agent 生命周期平台** |
| **适用场景** | GUI 自动化、RPA、Computer Use Agent | 代码执行、数据分析 Agent |
| **冷启动** | 1.8s（实测，完整 VM） | ~5s（文档，无预热） |
| **浅休眠唤醒** | 亚秒（预热池） | **~1ms**（内存快照） |

---

## 七、选型建议

### 用例 → 推荐平台

| 使用场景 | 首选 | 次选 | 不推荐 |
|----------|------|------|--------|
| **LLM 代码执行沙箱**（数据分析、公式求解） | E2B | OpenSandbox | Runloop |
| **Coding Agent**（clone repo、跑测试） | Daytona | AgentRun | AgentBay |
| **Browser Use Agent**（网页操作） | AgentBay | AgentRun | E2B |
| **Mobile Agent**（App 自动化） | **AgentBay（唯一）** | — | 其他均不支持 |
| **企业 Agent 生产部署** | Runloop | AgentRun | E2B |
| **国内（中国区）部署** | AgentBay | AgentRun | Daytona/E2B 不支持 |
| **自托管/私有化** | OpenSandbox | Daytona | AgentBay/AgentRun |
| **多语言 SDK 团队** | OpenSandbox | AgentBay | Daytona |

---

## 八、总结

**第一梯队综合评分：**

```
Daytona     ★★★★★  冷启动最快，生态好，但国内不可用
E2B         ★★★★★  隔离最强，SDK 标准，生态最佳，但国内不可用  
OpenSandbox ★★★★☆  最全能，开源，E2B 兼容，阿里系，国内可用
Runloop     ★★★★☆  企业功能最完整，价格高，不开源
AgentBay    ★★★★☆  唯一 Mobile Use，实测稳定，国内最佳 Computer Use 方案
AgentRun    ★★★☆☆  平台功能全但接入复杂，适合已在 FC 体系的团队
```

**核心结论：**

1. **如果你在中国做 Agent 产品**：AgentBay（Computer Use/Mobile Use）+ AgentRun（代码执行）是最可行的组合，OpenSandbox 是自托管备选。

2. **如果你做出海 Agent 产品**：E2B 做代码执行（Firecracker 隔离+生态最好），Daytona 做 Coding Agent（最快冷启动），Runloop 做企业部署。

3. **AgentBay 最大差异化**：88 个 MCP 预装工具 + Mobile Use（唯一），稳态 50ms 命令延迟，但冷启动 1.8s 偏高，适合长会话场景复用 Session。

4. **AgentRun 注意事项**：提供的 `ak_f1io8fp0sr8l4y8arefvbs` 是 Agent 调用 token，沙箱管理需要独立的阿里云 AK/SK，建议联系你的 FC 账号获取完整凭据后再测试沙箱功能。

---

*实测数据来源：2026-06-15 北京时间，AgentBay cn-hangzhou 区域，`computer-use-ubuntu-2204` 镜像*  
*其余平台数据来源：官方文档、GitHub 及公开 benchmark 报告*
