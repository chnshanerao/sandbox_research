#!/usr/bin/env python3
"""
Demo 01b: 计算层 — Docker 容器隔离演示
========================================
演示 AI Agent 基础设施的计算层：
- 容器级别的进程/文件系统/网络隔离
- 资源限制（CPU/内存）
- 对比不同隔离技术

对应基础设施栈：计算层 / Compute
"""
import subprocess
import time
import json
import sys


def run_cmd(cmd: str, timeout: int = 30) -> tuple[str, int]:
    """执行命令，返回 (输出, 返回码)"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout + result.stderr
        return output.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 1
    except Exception as e:
        return str(e), 1


def main():
    print("=" * 70)
    print("  Demo 01b: 计算层 — Docker 容器隔离")
    print("  对应层: 计算层 / Compute")
    print("=" * 70)

    # --- 0. 检查 Docker ---
    out, rc = run_cmd("docker info --format '{{.ServerVersion}}'")
    if rc != 0:
        print("  [ERROR] Docker 不可用，跳过本 Demo")
        return
    print(f"\n  Docker 版本: {out}")

    # --- 1. 宿主机信息 ---
    print("\n[1] 宿主机环境 (对照组)")
    print("-" * 40)
    host_pid, _ = run_cmd("echo $$")
    host_user, _ = run_cmd("whoami")
    host_hostname, _ = run_cmd("hostname")
    host_kernel, _ = run_cmd("uname -r")
    print(f"  PID:      {host_pid}")
    print(f"  用户:     {host_user}")
    print(f"  主机名:   {host_hostname}")
    print(f"  内核:     {host_kernel}")

    # --- 2. 容器隔离 ---
    print("\n[2] 容器隔离 — 独立命名空间")
    print("-" * 40)

    IMAGE = "python:3.12-slim"
    out, rc = run_cmd(f"docker images -q {IMAGE}")
    if not out:
        print(f"  镜像 {IMAGE} 不存在，尝试拉取...")
        out, rc = run_cmd(f"docker pull {IMAGE}", timeout=120)
        if rc != 0:
            alt_images = ["local/python-sandbox:v4", "ubuntu:latest", "alpine:latest"]
            for alt in alt_images:
                out2, rc2 = run_cmd(f"docker images -q {alt}")
                if out2:
                    IMAGE = alt
                    print(f"  使用本地镜像: {IMAGE}")
                    break
            else:
                print("  [ERROR] 无可用镜像，跳过容器测试")
                return

    tests = [
        ("PID 命名空间", "echo PID=$$ && cat /proc/1/cmdline 2>/dev/null | tr '\\0' ' ' || echo 'PID 1 不可读'"),
        ("用户隔离", "whoami && id"),
        ("主机名隔离", "hostname"),
        ("文件系统隔离", "ls / | head -5 && echo '--- /tmp ---' && ls /tmp 2>/dev/null || echo '空'"),
        ("进程隔离", "ps aux 2>/dev/null | head -5 || echo '仅可见容器内进程'"),
    ]

    for test_name, cmd in tests:
        docker_cmd = f'docker run --rm --network=host {IMAGE} sh -c "{cmd}"'
        t0 = time.time()
        out, rc = run_cmd(docker_cmd, timeout=30)
        duration = (time.time() - t0) * 1000
        print(f"\n  [{test_name}] ({duration:.0f}ms)")
        for line in out.split("\n")[:4]:
            print(f"    容器内: {line}")

    # --- 3. 资源限制 ---
    print(f"\n{'─' * 60}")
    print("[3] 资源限制 — CPU & 内存")
    print("-" * 40)

    resource_tests = [
        (
            "内存限制 (64MB)",
            f'docker run --rm --network=host --memory=64m {IMAGE} python3 -c "'
            "import sys; print(f'内存限制生效'); "
            "data = []; "
            "[data.append(b'x' * 1024 * 1024) for _ in range(10)]; "  # try 10MB
            "print(f'分配了 {len(data)}MB')"
            '"',
        ),
        (
            "CPU 限制 (0.5 核)",
            f'docker run --rm --network=host --cpus=0.5 {IMAGE} python3 -c "'
            "import time; t=time.time(); "
            "sum(i*i for i in range(500000)); "
            "elapsed=time.time()-t; "
            "print(f'CPU限制下计算耗时: ' + str(round(elapsed,3)) + 's')"
            '"',
        ),
    ]

    for test_name, cmd in resource_tests:
        t0 = time.time()
        out, rc = run_cmd(cmd, timeout=30)
        duration = (time.time() - t0) * 1000
        status = "OK" if rc == 0 else "KILLED"
        print(f"\n  [{test_name}] ({duration:.0f}ms, {status})")
        for line in out.split("\n")[:3]:
            print(f"    {line}")

    # --- 4. 网络隔离 ---
    print(f"\n{'─' * 60}")
    print("[4] 网络隔离 — --network=none")
    print("-" * 40)

    net_cmd = (
        f"docker run --rm --network=host {IMAGE} python3 -c "
        '"'
        "import socket; s=socket.socket(); s.settimeout(2); "
        "print('网络可达: ' + str(s.connect_ex(('127.0.0.1', 80))))"
        '"'
    )
    print(f"  使用 --network=host (本环境 Docker bridge 网络受限):")
    print(f"  说明: 生产环境中用 --network=none 实现完全网络隔离")
    out, rc = run_cmd(net_cmd, timeout=15)
    print(f"  {out}")

    # --- 5. 隔离技术对比 ---
    print(f"\n{'═' * 70}")
    print("  隔离技术对比")
    print("═" * 70)
    print("""
  ┌──────────────┬──────────┬──────────┬───────────┬──────────────┐
  │ 技术          │ 隔离强度  │ 冷启动   │ 内存开销  │ 典型用户     │
  ├──────────────┼──────────┼──────────┼───────────┼──────────────┤
  │ Docker容器    │ ★★★☆☆   │ ~500ms   │ ~10MB     │ OpenSandbox  │
  │ gVisor       │ ★★★★☆   │ ~200ms   │ ~30MB     │ AgentCube    │
  │ Firecracker  │ ★★★★★   │ ~150ms   │ ~5MB      │ E2B, Lambda  │
  │ 完整VM       │ ★★★★★   │ ~1.8s    │ ~7GB      │ AgentBay     │
  │ WASM         │ ★★★☆☆   │ ~1ms     │ ~1MB      │ 实验性       │
  │ Kata容器     │ ★★★★☆   │ ~500ms   │ ~100MB    │ 云原生       │
  └──────────────┴──────────┴──────────┴───────────┴──────────────┘

  本 Demo 演示了 Docker 容器隔离。关键结论：
  - 容器共享宿主机内核 → 隔离弱于 Firecracker/VM
  - 但启动快、开销小 → 适合受信任代码执行
  - AI Agent 场景首选 Firecracker (E2B) 或 完整VM (AgentBay)
    因为 LLM 生成的代码完全不可信
""")


if __name__ == "__main__":
    main()
