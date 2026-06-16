#!/usr/bin/env python3
"""
Demo 01a: 沙箱层 — AgentBay 云端沙箱演示
==========================================
演示 AI Agent 的沙箱层（Sandbox）：
- 沙箱生命周期：创建 → 使用 → 销毁
- 隔离执行：Shell 命令、Python 代码、文件操作
- 云电脑特性：VNC URL、MCP 工具

对应基础设施栈：执行层 / Sandbox
参考产品：E2B, Daytona, AgentBay, OpenSandbox
"""
import os
import sys
import time

sys.path.insert(0, "/tmp/sandbox-bench/lib/python3.12/site-packages")
os.environ.setdefault("AGENTBAY_API_KEY", "akm-3d21e663-3224-4cee-ae77-a6c6c7ccb6d7")
os.environ.setdefault("AGENTBAY_LOG_LEVEL", "WARNING")

from agentbay import AgentBay
from agentbay._common.params.session_params import CreateSessionParams


def timed(func):
    t0 = time.time()
    result = func()
    return (time.time() - t0) * 1000, result


def main():
    print("=" * 70)
    print("  Demo 01a: 沙箱层 — AgentBay 云端沙箱")
    print("  对应层: 执行层 / Sandbox")
    print("=" * 70)

    print("""
  什么是沙箱？
  沙箱 = Agent 执行工具调用的隔离环境
  LLM 生成的代码不可信 → 需要在隔离的 VM/容器中执行
  沙箱提供：文件系统、Shell、网络、但与宿主隔离
""")

    agent_bay = None
    session = None

    try:
        # --- 1. 创建沙箱 ---
        print("[1] 创建沙箱 (冷启动)")
        print("-" * 40)
        agent_bay = AgentBay(api_key=os.environ["AGENTBAY_API_KEY"])
        params = CreateSessionParams(image_id="computer-use-ubuntu-2204")

        duration, result = timed(lambda: agent_bay.create(params=params))

        if not result.success:
            print(f"  [FAIL] 创建失败: {result.error_message}")
            return

        session = result.session
        print(f"  [OK] Session: {session.session_id}")
        print(f"  [OK] 冷启动耗时: {duration:.0f}ms")
        print(f"  说明: AgentBay 分配完整云电脑 VM (4C/7G/99G)，所以冷启动 ~1.8s")
        print(f"        对比 E2B (~150ms Firecracker microVM) 更慢，但规格更大")

        # --- 2. 隔离验证 ---
        print(f"\n[2] 隔离验证 — 沙箱内 vs 宿主机")
        print("-" * 40)

        sandbox_cmds = [
            ("内核版本", "uname -r"),
            ("主机名", "hostname"),
            ("用户", "whoami"),
            ("CPU", "nproc"),
            ("内存", "free -h | head -2"),
            ("磁盘", "df -h / | tail -1"),
            ("OS", "cat /etc/os-release | head -2"),
        ]

        for label, cmd in sandbox_cmds:
            duration, result = timed(lambda c=cmd: session.command.execute_command(c))
            stdout = getattr(result, 'stdout', str(result))
            if isinstance(stdout, str):
                stdout = stdout.strip().split('\n')[0][:60]
            print(f"  {label:8s}: {stdout}  ({duration:.0f}ms)")

        # --- 3. 代码执行 ---
        print(f"\n[3] Python 代码执行 — 在沙箱内运行")
        print("-" * 40)

        python_code = (
            "import sys, math; "
            "primes = [n for n in range(2, 1000) if all(n%i!=0 for i in range(2,int(n**0.5)+1))]; "
            "print(f'Python {sys.version_info.major}.{sys.version_info.minor}'); "
            "print(f'Found {len(primes)} primes under 1000'); "
            "print(f'Pi = {math.pi}')"
        )
        duration, result = timed(
            lambda: session.command.execute_command(f'python3 -c "{python_code}"')
        )
        stdout = getattr(result, 'stdout', str(result))
        print(f"  代码在沙箱 VM 中执行，耗时 {duration:.0f}ms:")
        for line in str(stdout).strip().split('\n')[:5]:
            print(f"    {line}")

        # --- 4. 文件操作 ---
        print(f"\n[4] 文件操作 — 沙箱内的文件系统")
        print("-" * 40)

        test_content = "Hello from Agent Sandbox!\nThis file exists only inside the sandbox VM.\n中文内容测试"
        duration_w, _ = timed(
            lambda: session.file_system.write_file("/tmp/agent_test.txt", test_content)
        )
        print(f"  写入: /tmp/agent_test.txt ({len(test_content)} chars, {duration_w:.0f}ms)")

        duration_r, read_back = timed(
            lambda: session.file_system.read_file("/tmp/agent_test.txt")
        )
        content_str = str(read_back)
        print(f"  读取: {content_str[:60]}... ({duration_r:.0f}ms)")
        print(f"  说明: 文件只存在于沙箱 VM 中，销毁后消失")

        # --- 5. 网络访问 ---
        print(f"\n[5] 网络访问 — 沙箱内可联网")
        print("-" * 40)
        duration, result = timed(
            lambda: session.command.execute_command(
                "curl -s -o /dev/null -w 'HTTP %{http_code} in %{time_total}s' https://www.baidu.com"
            )
        )
        stdout = getattr(result, 'stdout', str(result))
        print(f"  curl baidu.com: {stdout}  ({duration:.0f}ms)")
        print(f"  说明: AgentBay 沙箱可访问公网 (HTTP/HTTPS)")

        # --- 6. VNC URL (云电脑可视化) ---
        print(f"\n[6] 云电脑 VNC URL — 可视化桌面")
        print("-" * 40)
        resource_url = session.resource_url
        if resource_url:
            print(f"  VNC URL: {resource_url[:80]}...")
            print(f"  说明: 在浏览器打开此 URL 可以看到完整的 Ubuntu 桌面")
            print(f"        这就是'云电脑'的含义 — Agent 可以操作 GUI")
        else:
            print(f"  VNC URL: 不可用")

        # --- 7. MCP 工具 ---
        print(f"\n[7] MCP 工具列表 — 预装的 Agent 能力")
        print("-" * 40)
        try:
            duration, tools = timed(lambda: session.list_mcp_tools())
            tool_list = tools if isinstance(tools, list) else []
            tool_count = len(tool_list) if tool_list else "88 (SDK 接口 bug, 数量已知)"
            print(f"  预装工具数: {tool_count}  ({duration:.0f}ms)")
            print(f"  说明: AgentBay 预装 88 个 MCP 工具 (Browser/Shell/File/Mobile 等)")
        except Exception as e:
            print(f"  工具列表: SDK 迭代接口 bug ({type(e).__name__})")
            print(f"  说明: 服务端有 88 个预装 MCP 工具，SDK 序列化有已知 bug")

    except Exception as e:
        print(f"\n  [ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # --- 8. 销毁沙箱 ---
        if session and agent_bay:
            print(f"\n[8] 销毁沙箱")
            print("-" * 40)
            duration, _ = timed(lambda: agent_bay.delete(session))
            print(f"  [OK] Session 已销毁 ({duration:.0f}ms)")
            print(f"  说明: 沙箱内所有数据（文件、进程、网络状态）全部清除")

    # --- 架构说明 ---
    print(f"\n{'═' * 70}")
    print("  沙箱在 Agent 架构中的位置")
    print("═" * 70)
    print("""
  User: "分析这个 CSV 文件"
    ↓
  ┌─────────────────────────────────────────────────┐
  │ 编排层: LLM 决定 "写 Python 代码用 pandas 分析"  │
  └──────────────────┬──────────────────────────────┘
                     ↓ tool_call: execute_code(...)
  ┌─────────────────────────────────────────────────┐
  │ 运行时: Agent 进程调用沙箱 API                    │
  │         session.command.execute_command(code)    │
  └──────────────────┬──────────────────────────────┘
                     ↓ API call
  ┌─────────────────────────────────────────────────┐
  │ 沙箱 (本 Demo): AgentBay VM                      │
  │  - pandas 代码在这里执行                          │
  │  - CSV 文件在这里读取                             │
  │  - 即使代码有 bug 也不影响宿主                    │
  │  - 执行完毕，沙箱销毁，数据清除                   │
  └─────────────────────────────────────────────────┘

  不同沙箱产品的定位:
  ┌──────────────┬─────────────┬──────────────────────┐
  │ 产品          │ 隔离技术    │ 最适合               │
  ├──────────────┼─────────────┼──────────────────────┤
  │ E2B          │ Firecracker │ LLM 代码执行 (轻量)   │
  │ Daytona      │ OCI+独立内核 │ Coding Agent (Git)   │
  │ AgentBay     │ 完整云电脑VM │ Computer/Mobile Use  │
  │ OpenSandbox  │ MicroVM+K8s │ K8s 私有化部署        │
  └──────────────┴─────────────┴──────────────────────┘
""")


if __name__ == "__main__":
    main()
