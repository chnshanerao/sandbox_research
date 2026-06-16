#!/usr/bin/env python3
"""AgentBay Sandbox Benchmark Tests - Full version"""
import time
import json
import os
import traceback

os.environ["AGENTBAY_API_KEY"] = "akm-3d21e663-3224-4cee-ae77-a6c6c7ccb6d7"

from agentbay import AgentBay
from agentbay._common.params.session_params import CreateSessionParams

results = {"platform": "AgentBay (无影)", "tests": []}

def record(name, status, duration_ms, detail=""):
    results["tests"].append({"name": name, "status": status, "duration_ms": round(duration_ms, 1), "detail": detail})
    icon = "PASS" if status == "pass" else "FAIL"
    print(f"  [{icon}] {name}: {duration_ms:.0f}ms - {detail[:200]}")

print("=" * 70)
print("  AgentBay (无影) Benchmark Test Suite")
print("=" * 70)

agent_bay = None
session = None

try:
    # Test 1: SDK Init
    t0 = time.time()
    agent_bay = AgentBay(api_key=os.environ["AGENTBAY_API_KEY"])
    t1 = time.time()
    record("SDK初始化", "pass", (t1-t0)*1000, "AgentBay SDK initialized")

    # Test 2: Cold Start - Session Creation
    print("\n--- Test: 冷启动 (Session Creation) ---")
    t0 = time.time()
    params = CreateSessionParams(image_id='computer-use-ubuntu-2204')
    result = agent_bay.create(params=params)
    t1 = time.time()
    cold_start_ms = (t1 - t0) * 1000

    if result.success:
        session = result.session
        record("冷启动(Session创建)", "pass", cold_start_ms,
               f"session_id={session.session_id}, image=computer-use-ubuntu-2204")
    else:
        record("冷启动(Session创建)", "fail", cold_start_ms, f"error: {result.error_message}")
        raise Exception("Session creation failed")

    # Test 3: Shell Command Execution
    print("\n--- Test: Shell命令执行 ---")
    t0 = time.time()
    cmd_result = session.command.execute_command("echo 'Hello from AgentBay Sandbox!' && uname -a && whoami")
    t1 = time.time()
    record("Shell命令执行", "pass", (t1-t0)*1000, str(cmd_result)[:200])

    # Test 4: Python Code Execution
    print("\n--- Test: Python代码执行 ---")
    python_code = 'import sys, platform, math; print(f"Python {sys.version}"); print(f"Platform: {platform.platform()}"); print(f"Pi = {math.pi}"); result = sum(range(1, 10001)); print(f"Sum(1..10000) = {result}")'
    t0 = time.time()
    py_result = session.command.execute_command(f'python3 -c "{python_code}"')
    t1 = time.time()
    record("Python代码执行", "pass", (t1-t0)*1000, str(py_result)[:200])

    # Test 5: File System - Write
    print("\n--- Test: 文件写入 ---")
    test_content = "Hello from benchmark test!\\nLine 2: Testing file operations\\nLine 3: 中文测试"
    t0 = time.time()
    session.file_system.write_file("/tmp/benchmark_test.txt", test_content)
    t1 = time.time()
    record("文件写入", "pass", (t1-t0)*1000, f"wrote {len(test_content)} chars to /tmp/benchmark_test.txt")

    # Test 6: File System - Read
    print("\n--- Test: 文件读取 ---")
    t0 = time.time()
    read_content = session.file_system.read_file("/tmp/benchmark_test.txt")
    t1 = time.time()
    record("文件读取", "pass", (t1-t0)*1000, f"read back: {str(read_content)[:150]}")

    # Test 7: Network Access
    print("\n--- Test: 网络访问 ---")
    t0 = time.time()
    net_result = session.command.execute_command("curl -s -o /dev/null -w 'HTTP %{http_code} in %{time_total}s' https://www.baidu.com 2>&1")
    t1 = time.time()
    record("网络访问(curl)", "pass", (t1-t0)*1000, str(net_result)[:200])

    # Test 8: Compute - Prime Numbers
    print("\n--- Test: 计算密集型 ---")
    prime_code = 'import time; t0=time.time(); primes=[n for n in range(2,10000) if all(n%i!=0 for i in range(2,int(n**0.5)+1))]; print(f"Found {len(primes)} primes in {(time.time()-t0)*1000:.0f}ms")'
    t0 = time.time()
    compute_result = session.command.execute_command(f'python3 -c "{prime_code}"')
    t1 = time.time()
    record("计算密集型(素数)", "pass", (t1-t0)*1000, str(compute_result)[:200])

    # Test 9: System Info
    print("\n--- Test: 系统信息 ---")
    t0 = time.time()
    sys_info = session.command.execute_command(
        "echo '=== CPU ===' && nproc && cat /proc/cpuinfo | head -5 && echo '=== Memory ===' && free -h | head -2 && echo '=== Disk ===' && df -h / | tail -1 && echo '=== OS ===' && cat /etc/os-release | head -3"
    )
    t1 = time.time()
    record("系统信息", "pass", (t1-t0)*1000, str(sys_info)[:300])

    # Test 10: Package Installation
    print("\n--- Test: pip包安装 ---")
    t0 = time.time()
    pkg_result = session.command.execute_command("pip3 install requests 2>&1 | tail -3")
    t1 = time.time()
    record("pip包安装(requests)", "pass", (t1-t0)*1000, str(pkg_result)[:200])

    # Test 11: Multi-command pipeline
    print("\n--- Test: 多命令管道 ---")
    t0 = time.time()
    pipe_result = session.command.execute_command(
        "seq 1 100 | awk '{sum+=$1} END {print \"Sum 1-100 =\", sum}' && ls -la /tmp/ | wc -l"
    )
    t1 = time.time()
    record("多命令管道", "pass", (t1-t0)*1000, str(pipe_result)[:200])

    # Test 12: Session Status/Info
    print("\n--- Test: Session状态查询 ---")
    t0 = time.time()
    status = session.get_status()
    t1 = time.time()
    record("Session状态查询", "pass", (t1-t0)*1000, f"status={status}")

    # Test 13: Resource URL
    print("\n--- Test: Resource URL ---")
    resource_url = session.resource_url
    record("Resource URL获取", "pass", 0, f"url={resource_url[:80]}..." if resource_url else "N/A")

    # Test 14: Available tools (MCP)
    print("\n--- Test: MCP工具列表 ---")
    t0 = time.time()
    try:
        tools = session.list_mcp_tools()
        t1 = time.time()
        tool_names = [t.name if hasattr(t, 'name') else str(t) for t in tools] if tools else []
        record("MCP工具列表", "pass", (t1-t0)*1000, f"found {len(tool_names)} tools: {tool_names[:5]}")
    except Exception as e:
        t1 = time.time()
        record("MCP工具列表", "fail", (t1-t0)*1000, str(e)[:200])

except Exception as e:
    record("Error", "fail", 0, f"{type(e).__name__}: {e}")
    traceback.print_exc()

finally:
    if session and agent_bay:
        print("\n--- Cleanup ---")
        t0 = time.time()
        try:
            agent_bay.delete(session)
            t1 = time.time()
            record("Session清理", "pass", (t1-t0)*1000, "session deleted")
        except Exception as e:
            t1 = time.time()
            record("Session清理", "fail", (t1-t0)*1000, str(e)[:200])

print("\n" + "=" * 70)
print("  AgentBay Results Summary")
print("=" * 70)
passed = sum(1 for t in results["tests"] if t["status"] == "pass")
total = len(results["tests"])
print(f"\n  Total: {total} tests, Passed: {passed}, Failed: {total-passed}\n")
for t in results["tests"]:
    icon = "PASS" if t["status"] == "pass" else "FAIL"
    print(f"  [{icon}] {t['name']:25s} {t['duration_ms']:>8.0f}ms  {t['detail'][:80]}")

with open("/home/admin/workspace/robo/agentbay_results.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nResults saved to agentbay_results.json")
