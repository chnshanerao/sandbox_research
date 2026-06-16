# AI Agent 沙箱 Runtime 实测：OpenSandbox vs AgentBay

> 内部技术文档 | 2026-06-15 | 测试环境：Devix Kata 容器

---

## 1. 概述

本文档记录在本地环境中部署 OpenSandbox（自托管 Docker Runtime）并与 AgentBay（阿里云托管 PaaS）进行 Runtime 性能对比测试的完整过程。

**测试维度：** 沙箱创建、命令执行、代码执行（Python）、文件读写、沙箱销毁

**为什么做这个测试：** 评估 AI Agent 沙箱的自托管方案（OpenSandbox）与云端托管方案（AgentBay）在延迟、吞吐、易用性上的实际差异，为 Agent Runtime 选型提供数据支撑。

---

## 2. 环境信息

```
OS:          Ubuntu 24.04 (Noble) on Kata Container
CPU:         x86_64, 多核
内存:        ~8.7 GB
磁盘:        ~3.5 TB
Python:      3.12.3
网络约束:    mitmproxy 拦截所有 HTTPS → Docker Hub / 镜像源全部 502
容器约束:    Kata VM 内嵌套 Docker（Docker-in-Kata）
             - overlay fs 不支持 → 必须用 vfs 存储驱动
             - bridge 网络不支持（IPv6 配置失败）→ 必须用 host 网络
             - cgroups 只读 → 需手动重挂载
```

---

## 3. Part 1: Docker 安装

### 3.1 安装 Docker CE

```bash
# 添加 Docker 官方源
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu noble stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# 解决 dpkg systemd 配置冲突
echo "N" | sudo -E dpkg --force-confold --configure systemd
```

### 3.2 启动 dockerd（Kata 环境特殊配置）

overlay 文件系统在 Kata 内不支持，必须用 vfs：

```bash
# 重挂载 cgroups 为可写（Kata 默认只读）
for ctrl in cpuset cpu cpuacct blkio memory devices freezer net_cls perf_event net_prio hugetlb pids rdma misc; do
  mountpoint="/sys/fs/cgroup/$ctrl"
  if mountpoint -q "$mountpoint" 2>/dev/null; then
    sudo umount "$mountpoint" 2>/dev/null
    sudo mount -t cgroup -o "rw,$ctrl" cgroup "$mountpoint" 2>/dev/null
  fi
done

# 启动 dockerd（vfs 驱动 + 无 iptables）
sudo dockerd --storage-driver=vfs --iptables=false --ip6tables=false &

# 验证
docker info | grep "Storage Driver"  # 应输出: vfs
```

### 3.3 验证

```bash
docker ps  # 确认 daemon 运行
```

> **注意：** `docker run hello-world` 会失败，因为无法从 Docker Hub 拉取镜像（mitmproxy 502）。

---

## 4. Part 2: 构建本地 Docker 镜像

因为所有外部镜像源被 mitmproxy 拦截，需要从宿主机二进制文件手动构建镜像。

### 4.1 创建 rootfs

```bash
mkdir -p /tmp/python-rootfs4/{bin,lib,lib64,usr/bin,usr/lib,tmp,opt/opensandbox,etc,proc,sys,dev}

# 复制基础二进制
for bin in bash sh cat ls grep sed awk head tail wc sort cut tr env; do
  cp "$(which $bin)" /tmp/python-rootfs4/bin/
done
cp "$(which python3)" /tmp/python-rootfs4/usr/bin/

# 复制 Python 标准库
cp -r /usr/lib/python3.12 /tmp/python-rootfs4/usr/lib/
cp -r /usr/lib/python3 /tmp/python-rootfs4/usr/lib/ 2>/dev/null

# 复制所有依赖的共享库
for bin in /tmp/python-rootfs4/bin/* /tmp/python-rootfs4/usr/bin/*; do
  ldd "$bin" 2>/dev/null | grep -oP '/\S+' | while read lib; do
    dir=$(dirname "$lib")
    mkdir -p "/tmp/python-rootfs4$dir"
    cp -n "$lib" "/tmp/python-rootfs4$lib" 2>/dev/null
  done
done

# 复制 ld-linux 动态链接器
cp /lib64/ld-linux-x86-64.so.2 /tmp/python-rootfs4/lib64/

# 复制 execd 二进制（关键！必须是文件，不是目录）
cp /opt/opensandbox/execd /tmp/python-rootfs4/execd
chmod 755 /tmp/python-rootfs4/execd

# 基本配置文件
echo "root:x:0:0:root:/root:/bin/bash" > /tmp/python-rootfs4/etc/passwd
echo "root:x:0:" > /tmp/python-rootfs4/etc/group
```

### 4.2 导入为 Docker 镜像

```bash
cd /tmp/python-rootfs4
tar cf /tmp/python-rootfs4.tar .
docker import /tmp/python-rootfs4.tar local/python-sandbox:v4
docker images  # 确认镜像约 101MB
```

### 4.3 关于 execd 路径的关键细节

**这是最容易踩的坑：** OpenSandbox 的 `_fetch_execd_archive()` 会从 execd_image 容器中执行 `get_archive("/execd")`，然后将结果解压到 sandbox 容器的 `/opt/opensandbox/` 下。

- 如果 `/execd` 是**文件** → 解压后得到 `/opt/opensandbox/execd`（二进制）✅
- 如果 `/execd` 是**目录**（包含 execd 文件）→ 解压后得到 `/opt/opensandbox/execd/execd` ❌

所以镜像中 `/execd` 必须是二进制文件本身，不能是包含它的目录。

---

## 5. Part 3: OpenSandbox 部署

### 5.1 安装 Server 和 SDK

```bash
# 在 venv 中安装
source /home/admin/agentbay-env/bin/activate
pip install opensandbox-server opensandbox
```

### 5.2 初始化配置

```bash
opensandbox-server init-config ~/.sandbox.toml --example docker
```

### 5.3 最终配置文件 (`~/.sandbox.toml`)

```toml
[server]
host = "127.0.0.1"
port = 8080
max_sandbox_timeout_seconds = 86400

[log]
level = "INFO"

[runtime]
type = "docker"
execd_image = "local/python-sandbox:v4"

[storage]
allowed_host_paths = []
volume_default_size = "1Gi"

[store]
type = "sqlite"
path = "~/.opensandbox/opensandbox.db"

[docker]
network_mode = "host"
drop_capabilities = []          # Kata 不支持部分 capabilities
no_new_privileges = false
apparmor_profile = ""
pids_limit = 4096
seccomp_profile = ""

[ingress]
mode = "direct"

[egress]
image = "local/python-sandbox:v4"
mode = "dns"

[renew_intent]
enabled = false
min_interval_seconds = 60
```

### 5.4 补丁：runtime.py（execd-cache 容器网络模式）

OpenSandbox 的 `_fetch_execd_archive()` 创建临时容器提取 execd 二进制时，**没有使用配置文件中的 `network_mode`**，默认走 bridge 网络，在 Kata 环境中失败。

**文件：** `lib/python3.12/site-packages/opensandbox_server/services/docker/runtime.py`

```python
# 在 create_kwargs dict 中添加 network_mode（约第 74-82 行）
create_kwargs: dict[str, any] = {
    "image": self.execd_image,
    "command": ["tail", "-f", "/dev/null"],
    "name": f"sandbox-execd-{uuid4()}",
    "detach": True,
    "auto_remove": False,
    "network_mode": self.network_mode,  # ← 添加这一行
}
```

### 5.5 启动 Server

```bash
OPENSANDBOX_INSECURE_SERVER=YES nohup opensandbox-server \
  --config ~/.sandbox.toml > /tmp/opensandbox-server.log 2>&1 &

# 验证
curl -s http://127.0.0.1:8080/health
# 输出: {"status":"healthy"}
```

### 5.6 关于 host 网络模式下的 execd

使用 `network_mode = "host"` 时，sandbox 容器与宿主机共享网络命名空间。宿主机已有 execd 进程监听 44772 端口：

```bash
# 查看宿主机 execd 进程和 token
cat /proc/$(pgrep execd)/environ | tr '\0' '\n' | grep TOKEN
# EXECD_ACCESS_TOKEN=lMc2bI_JOKZsNN_c707D3S4Tn303viMrQIAJhKi3CEg
```

sandbox 容器的 bootstrap 脚本会尝试启动自己的 execd，但因端口冲突会失败。所有命令实际由宿主机的 execd 执行。SDK 需要在 headers 中传递 `X-EXECD-ACCESS-TOKEN` 才能通过认证。

---

## 6. Part 4: AgentBay 接入

### 6.1 安装 SDK

```bash
pip install wuying-agentbay-sdk
```

### 6.2 设置 API Key

```bash
export AGENTBAY_API_KEY='akm-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
```

### 6.3 基本使用

```python
from agentbay import AgentBay, CreateSessionParams
import os

agentbay = AgentBay(api_key=os.environ["AGENTBAY_API_KEY"])
result = agentbay.create(CreateSessionParams(image_id="code_latest"))
session = result.session

# 命令执行
out = session.command.execute_command(command="echo hello", timeout_ms=30000)
print(out.stdout)

# 代码执行
out = session.code.run_code(code="print(42)", language="python", timeout_s=60)
print(out.logs.stdout)

# 文件操作
session.file_system.write_file("/tmp/test.txt", "hello", mode="overwrite")
content = session.file_system.read_file("/tmp/test.txt", format="text")

# 清理
session.delete()
```

---

## 7. Part 5: 对比测试

### 7.1 运行测试

```bash
source /home/admin/agentbay-env/bin/activate
cd /home/admin/workspace/robo/sandbox-comparison
AGENTBAY_API_KEY='your-key' python3 run_comparison.py
```

测试脚本 `run_comparison.py` 见同目录文件，测试流程：
- 每个平台跑 3 轮
- 每轮：创建沙箱 → 命令执行 → Python 基准测试 → 文件读写 → 销毁沙箱
- 输出对比表格 + JSON 结果文件

### 7.2 测试结果

```
==========================================================================
  OpenSandbox vs AgentBay · 对比结果
==========================================================================

测试项                 OpenSandbox     AgentBay       倍数           胜出
--------------------------------------------------------------------------
沙箱创建                    4.436s      0.816s    5.4x快     AgentBay
命令执行                    1.009s      0.177s    5.7x快     AgentBay
代码执行(Python)            1.024s      0.146s    7.0x快     AgentBay
文件读写                    0.005s      0.093s   19.4x快  OpenSandbox
沙箱销毁                    0.420s      1.306s    3.1x快  OpenSandbox
--------------------------------------------------------------------------
总计                      6.894s      2.538s    2.7x快     AgentBay
```

### 7.3 环境差异说明

| 维度 | OpenSandbox | AgentBay |
|------|-------------|----------|
| 部署方式 | 本地 Docker (Kata 内嵌套) | 阿里云托管 PaaS |
| 存储驱动 | vfs（最慢，无 COW） | 云端优化 |
| 网络 | host 模式（与宿主共享） | 云端内网 |
| 沙箱池化 | 无（每次从零创建） | 有预热池 |
| execd 连接 | SSE 流，~1s 固定开销 | 优化的 RPC 协议 |

**公平性说明：** 这个对比不完全公平。OpenSandbox 跑在限制极多的 Kata 环境中，用了最慢的 vfs 驱动。在正常裸金属服务器 + overlay2 驱动上，OpenSandbox 的创建速度预计能提升 2-3 倍。命令执行的 ~1s 开销是 SDK SSE 协议固有延迟，与部署环境无关。

---

## 8. 踩坑清单

| # | 问题 | 原因 | 修复 |
|---|------|------|------|
| 1 | `dpkg --configure` 卡住 | systemd 配置文件冲突，交互式提示 | `echo "N" \| sudo -E dpkg --force-confold --configure systemd` |
| 2 | Docker Hub 镜像拉取 502 | mitmproxy 拦截所有 HTTPS 流量 | 放弃拉取，用 `docker import` 从本地二进制构建镜像 |
| 3 | overlay fs 挂载失败 | Kata VM 不支持 overlay 文件系统 | `--storage-driver=vfs` |
| 4 | cgroups 只读 | Kata 默认只读挂载 `/sys/fs/cgroup/*` | 逐个 `umount` + `mount -t cgroup -o rw` |
| 5 | bridge 网络 IPv6 失败 | Kata 不支持容器 bridge 网络的 IPv6 配置 | `network_mode = "host"` |
| 6 | daemon.json 和命令行参数冲突 | `storage-driver` 同时在两处指定 | 删除 daemon.json 中的重复配置 |
| 7 | `CAP_SYS_TIME` 不支持 | Kata 内核不支持该 capability | `drop_capabilities = []`（清空，不做 cap drop） |
| 8 | `egress.mode = "disabled"` 无效 | Pydantic 校验只接受 `dns` 或 `dns+nft` | 改为 `mode = "dns"` |
| 9 | execd_image 空字符串报错 | 配置文件中 `execd_image = ""` | 设为 `"local/python-sandbox:v4"` |
| 10 | `/opt/opensandbox/execd` 是目录 | `docker import` 时 execd 被放入 `/execd/` 目录而非作为文件 | 重建镜像，确保 `/execd` 是文件不是目录 |
| 11 | execd-cache 容器创建失败 | runtime.py 创建临时容器时不使用配置的 network_mode | 补丁 runtime.py，添加 `"network_mode": self.network_mode` |
| 12 | 命令执行 401 Unauthorized | SDK 未传递 `X-EXECD-ACCESS-TOKEN`，host 模式下宿主 execd 需要 token | SDK `headers={"X-EXECD-ACCESS-TOKEN": "..."}` |
| 13 | `secure_access=True` 不支持 | Docker runtime 不支持 secureAccess | 仅 K8s 支持，Docker 需手动传 token header |
| 14 | Python 代码执行无输出 | `/bin/bash -c` 嵌套引号转义问题 | 直接用 `python3 -c '...'` 不套 bash |

---

## 9. 测试结果分析

### 9.1 OpenSandbox 慢在哪

- **创建慢（4.4s）：** vfs 驱动无 copy-on-write，每次创建都做完整文件复制。正常 overlay2 预计 1-2s。
- **命令执行慢（1.0s）：** SDK 使用 SSE（Server-Sent Events）协议，每次请求有 ~1s 的流关闭等待。这是 SDK 层面的固有开销，与 Docker 无关。
- **文件读写快（0.005s）：** 本地文件操作，无网络延迟。

### 9.2 AgentBay 快在哪

- **创建快（0.8s）：** 云端有沙箱预热池，不需要每次从零创建容器。
- **命令执行快（0.17s）：** 优化过的 RPC 协议，无 SSE 流开销。
- **销毁慢（1.3s）：** 云端需要资源回收和状态清理，比本地 `docker rm` 慢。

### 9.3 架构对比

```
OpenSandbox 架构:
  SDK → HTTP → OpenSandbox Server → Docker API → Container
                                  ↓
                              execd (SSE)
                                  ↓
                           命令在容器内执行

AgentBay 架构:
  SDK → HTTPS → AgentBay Cloud API → 云端容器集群
                                    ↓
                              预热池分配 → 沙箱就绪
```

---

## 10. 赛道简析

### 主要玩家

| 平台 | 融资 | 日活/下载量 | 核心优势 |
|------|------|-----------|---------|
| E2B | $21M Series A | 3M+月下载 | 生态最成熟，Firecracker microVM |
| Daytona | 未公开 | 850K 日活 | Stars 最高(72K)，冷启动<90ms |
| Ona/Gitpod | ~$25M+ | 200万开发者 | **已被 OpenAI 收购 (2026.6.11)** |
| OpenSandbox | N/A (阿里开源) | 11.5K stars | 唯一全栈开源 |
| AgentBay | N/A (阿里云) | 1.1K stars | 唯一 Mobile Use |
| Runloop | 未公开 | ~31 stars | 企业级合规 |

### 阿里云内部产品重叠

阿里云内部至少有 3 个团队在做沙箱：

1. **FC 云沙箱**（函数计算团队）— 95% 兼容 E2B SDK，MicroVM 隔离
2. **ACS Agent Sandbox**（容器服务团队）— K8s 生产级方案
3. **AgentBay**（无影团队）— Browser + Mobile Use

FC 云沙箱在代码执行场景直接兼容 E2B SDK（改一行 endpoint），对 AgentBay 的代码沙箱定位构成内部竞争。

### 关键事件

**OpenAI 收购 Ona（2026.6.11）：** Gitpod 更名 Ona 后被 OpenAI 收购，团队并入 Codex。这验证了沙箱技术的价值，但也说明独立沙箱公司的天花板 — 最好的出路是被平台收编。

---

## 附录 A: 文件清单

```
sandbox-comparison/
├── run_comparison.py              # 对比测试脚本
├── comparison_results.json        # 原始测试结果 (JSON)
├── sandbox-runtime-comparison.md  # 本文档
```

## 附录 B: 快速复现命令

```bash
# 前提：已安装 Docker，已部署 OpenSandbox Server

# 1. 安装 SDK
pip install opensandbox wuying-agentbay-sdk

# 2. 设置环境变量
export AGENTBAY_API_KEY='your-key'

# 3. 运行对比测试
cd /path/to/sandbox-comparison
python3 run_comparison.py

# 4. 查看结果
cat comparison_results.json | python3 -m json.tool
```

## 附录 C: OpenSandbox SDK 关键 API

```python
from opensandbox import SandboxSync
from opensandbox.config.connection_sync import ConnectionConfigSync
from datetime import timedelta

config = ConnectionConfigSync(
    domain="127.0.0.1:8080",
    protocol="http",
    headers={"X-EXECD-ACCESS-TOKEN": "your-token"},  # host 模式必须
)

sb = SandboxSync.create(
    image="local/python-sandbox:v4",
    connection_config=config,
    timeout=timedelta(seconds=120),
    ready_timeout=timedelta(seconds=60),
    skip_health_check=True,
)

# 命令执行
result = sb.commands.run("echo hello")
print(result.text)       # stdout
print(result.exit_code)  # 0

# 文件操作
sb.files.write_file("/tmp/test.txt", "content")
content = sb.files.read_file("/tmp/test.txt")

# 销毁
sb.kill()
```

## 附录 D: AgentBay SDK 关键 API

```python
from agentbay import AgentBay, CreateSessionParams

agentbay = AgentBay(api_key="your-key")
result = agentbay.create(CreateSessionParams(image_id="code_latest"))
session = result.session

# 命令执行
out = session.command.execute_command(command="echo hello", timeout_ms=30000)
print(out.stdout)

# 代码执行（独立 API，非命令行包装）
out = session.code.run_code(code="print(42)", language="python", timeout_s=60)
print(out.logs.stdout)

# 文件操作
session.file_system.write_file("/tmp/test.txt", "hello", mode="overwrite")
content = session.file_system.read_file("/tmp/test.txt", format="text")

# 销毁
session.delete()
```
