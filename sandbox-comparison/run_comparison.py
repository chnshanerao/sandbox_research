#!/usr/bin/env python3
"""
OpenSandbox vs AgentBay · Runtime 对比测试
==========================================
测试维度: 沙箱创建、命令执行、代码执行、文件读写、沙箱销毁
"""
import os
import sys
import time
import json
import traceback
from datetime import timedelta

os.environ.setdefault("AGENTBAY_LOG_LEVEL", "WARNING")

ROUNDS = 3
PYTHON_BENCHMARK = r"""
import sys, time
sys.set_int_max_str_digits(50000)

def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

t = time.time()
r = fib(100000)
elapsed = time.time() - t
print(f"fib(100000): {len(str(r))} digits in {elapsed:.3f}s")

primes = []
for n in range(2, 10000):
    if all(n % i for i in range(2, int(n**0.5)+1)):
        primes.append(n)
print(f"primes < 10000: {len(primes)}")
print("BENCHMARK_OK")
"""


def timed(func):
    t0 = time.time()
    result = func()
    return time.time() - t0, result


class OpenSandboxTest:
    name = "OpenSandbox (本地Docker)"

    def __init__(self):
        from opensandbox import SandboxSync
        from opensandbox.config.connection_sync import ConnectionConfigSync
        self.SandboxSync = SandboxSync
        self.config = ConnectionConfigSync(
            domain="127.0.0.1:8080", protocol="http",
            headers={"X-EXECD-ACCESS-TOKEN": "lMc2bI_JOKZsNN_c707D3S4Tn303viMrQIAJhKi3CEg"},
        )
        self.sandbox = None

    def test_create(self):
        elapsed, _ = timed(lambda: self._create())
        return elapsed

    def _create(self):
        self.sandbox = self.SandboxSync.create(
            image="local/python-sandbox:v4",
            connection_config=self.config,
            timeout=timedelta(seconds=120),
            ready_timeout=timedelta(seconds=60),
            skip_health_check=True,
        )

    def test_command(self):
        elapsed, result = timed(
            lambda: self.sandbox.commands.run(
                "echo hello && uname -a && date"
            )
        )
        return elapsed, (result.text or "").strip()

    def test_code(self):
        elapsed, result = timed(
            lambda: self.sandbox.commands.run(
                f"python3 -c {repr(PYTHON_BENCHMARK.strip())}"
            )
        )
        return elapsed, (result.text or "").strip()

    def test_filesystem(self):
        content = "Hello OpenSandbox! 测试中文和特殊字符: @#$%^&*()\n" * 100

        def _do():
            self.sandbox.files.write_file("/tmp/test_file.txt", content)
            return self.sandbox.files.read_file("/tmp/test_file.txt")

        elapsed, read_back = timed(_do)
        match = content.strip() in (read_back or "").strip()
        return elapsed, match

    def test_destroy(self):
        elapsed, _ = timed(lambda: self.sandbox.kill())
        self.sandbox = None
        return elapsed


class AgentBayTest:
    name = "AgentBay (云端PaaS)"

    def __init__(self):
        from agentbay import AgentBay, CreateSessionParams
        self.CreateSessionParams = CreateSessionParams
        api_key = os.environ.get("AGENTBAY_API_KEY", "")
        if not api_key:
            raise RuntimeError("AGENTBAY_API_KEY not set")
        self.agentbay = AgentBay(api_key=api_key)
        self.session = None

    def test_create(self):
        elapsed, _ = timed(lambda: self._create())
        return elapsed

    def _create(self):
        result = self.agentbay.create(
            self.CreateSessionParams(image_id="code_latest")
        )
        self.session = result.session

    def test_command(self):
        elapsed, result = timed(
            lambda: self.session.command.execute_command(
                command="echo hello && uname -a && date",
                timeout_ms=30000,
            )
        )
        stdout = getattr(result, "stdout", "") or str(result)
        return elapsed, stdout.strip()

    def test_code(self):
        elapsed, result = timed(
            lambda: self.session.code.run_code(
                code=PYTHON_BENCHMARK.strip(),
                language="python",
                timeout_s=60,
            )
        )
        logs = getattr(result, "logs", None)
        if logs:
            stdout_list = getattr(logs, "stdout", []) or []
            stdout = "\n".join(stdout_list)
        else:
            stdout = getattr(result, "stdout", "") or str(result)
        return elapsed, stdout.strip()

    def test_filesystem(self):
        content = "Hello AgentBay! 测试中文和特殊字符: @#$%^&*()\n" * 100

        def _do():
            self.session.file_system.write_file(
                "/tmp/test_file.txt", content, mode="overwrite"
            )
            return self.session.file_system.read_file(
                "/tmp/test_file.txt", format="text"
            )

        elapsed, read_back = timed(_do)
        match = content.strip() in str(read_back or "").strip()
        return elapsed, match

    def test_destroy(self):
        elapsed, _ = timed(lambda: self.session.delete())
        self.session = None
        return elapsed


def run_suite(test_class, rounds=ROUNDS):
    results = {
        "name": test_class.name,
        "rounds": [],
        "errors": [],
    }

    for r in range(rounds):
        print(f"\n  --- Round {r+1}/{rounds} ---")
        round_data = {}
        tester = None
        try:
            tester = test_class()

            print(f"    [CREATE] ...", end="", flush=True)
            t = tester.test_create()
            round_data["create"] = t
            print(f" {t:.2f}s")

            print(f"    [COMMAND] ...", end="", flush=True)
            t, out = tester.test_command()
            round_data["command"] = t
            round_data["command_output"] = out[:200]
            print(f" {t:.2f}s")

            print(f"    [CODE] ...", end="", flush=True)
            t, out = tester.test_code()
            round_data["code"] = t
            round_data["code_output"] = out[:300]
            print(f" {t:.2f}s")

            print(f"    [FS] ...", end="", flush=True)
            t, match = tester.test_filesystem()
            round_data["filesystem"] = t
            round_data["fs_match"] = match
            print(f" {t:.2f}s (match={match})")

            print(f"    [DESTROY] ...", end="", flush=True)
            t = tester.test_destroy()
            round_data["destroy"] = t
            print(f" {t:.2f}s")

        except Exception as e:
            err_msg = f"Round {r+1}: {e}"
            results["errors"].append(err_msg)
            print(f"\n    [ERROR] {e}")
            traceback.print_exc()
            if tester:
                try:
                    if hasattr(tester, "sandbox") and tester.sandbox:
                        tester.sandbox.kill()
                    elif hasattr(tester, "session") and tester.session:
                        tester.session.delete()
                except Exception:
                    pass

        results["rounds"].append(round_data)

    return results


def avg(data, key):
    vals = [r[key] for r in data if key in r]
    return sum(vals) / len(vals) if vals else float("nan")


def print_comparison(os_results, ab_results):
    print("\n" + "=" * 74)
    print("  OpenSandbox vs AgentBay · 对比结果")
    print("=" * 74)

    metrics = [
        ("create", "沙箱创建"),
        ("command", "命令执行"),
        ("code", "代码执行(Python)"),
        ("filesystem", "文件读写"),
        ("destroy", "沙箱销毁"),
    ]

    header = f"{'测试项':<18} {'OpenSandbox':>12} {'AgentBay':>12} {'倍数':>8} {'胜出':>12}"
    print(f"\n{header}")
    print("-" * 74)

    total_os, total_ab = 0, 0
    for key, label in metrics:
        os_avg = avg(os_results["rounds"], key)
        ab_avg = avg(ab_results["rounds"], key)
        if os_avg != os_avg or ab_avg != ab_avg:
            print(f"{label:<18} {'N/A':>12} {'N/A':>12} {'N/A':>8} {'N/A':>12}")
            continue

        total_os += os_avg
        total_ab += ab_avg
        if os_avg < ab_avg:
            ratio = ab_avg / os_avg
            winner = "OpenSandbox"
            diff = f"{ratio:.1f}x快"
        else:
            ratio = os_avg / ab_avg
            winner = "AgentBay"
            diff = f"{ratio:.1f}x快"

        print(f"{label:<18} {os_avg:>10.3f}s {ab_avg:>10.3f}s {diff:>8} {winner:>12}")

    print("-" * 74)
    if total_ab == 0 or total_os == 0:
        print(f"{'总计':<18} {total_os:>10.3f}s {total_ab:>10.3f}s {'N/A':>8} {'N/A':>12}")
    elif total_os < total_ab:
        ratio = total_ab / total_os
        winner = "OpenSandbox"
        print(f"{'总计':<18} {total_os:>10.3f}s {total_ab:>10.3f}s {ratio:>6.1f}x快 {winner:>12}")
    else:
        ratio = total_os / total_ab
        winner = "AgentBay"
        print(f"{'总计':<18} {total_os:>10.3f}s {total_ab:>10.3f}s {ratio:>6.1f}x快 {winner:>12}")

    print("\n--- 环境信息 ---")
    print(f"  OpenSandbox: 本地 Docker (vfs driver), 同机单进程")
    print(f"  AgentBay:    阿里云托管 PaaS (code_latest), 远程云端")

    print("\n--- 命令执行输出 ---")
    for name, results in [("OpenSandbox", os_results), ("AgentBay", ab_results)]:
        if results["rounds"] and results["rounds"][0].get("command_output"):
            print(f"\n  [{name}]:")
            for line in results["rounds"][0]["command_output"].split("\n")[:3]:
                print(f"    {line}")

    print("\n--- 代码基准测试输出 ---")
    for name, results in [("OpenSandbox", os_results), ("AgentBay", ab_results)]:
        if results["rounds"] and results["rounds"][0].get("code_output"):
            print(f"\n  [{name}]:")
            for line in results["rounds"][0]["code_output"].split("\n")[:5]:
                print(f"    {line}")

    if os_results["errors"] or ab_results["errors"]:
        print("\n--- 错误记录 ---")
        for name, results in [("OpenSandbox", os_results), ("AgentBay", ab_results)]:
            for e in results["errors"]:
                print(f"  [{name}] {e}")

    print()


def main():
    print("=" * 60)
    print("  OpenSandbox vs AgentBay · Runtime 对比测试")
    print(f"  轮次: {ROUNDS} | 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n\n[1/2] 测试 OpenSandbox (本地 Docker)")
    print("-" * 40)
    os_results = run_suite(OpenSandboxTest, rounds=ROUNDS)

    print("\n\n[2/2] 测试 AgentBay (云端 code_latest)")
    print("-" * 40)
    ab_results = run_suite(AgentBayTest, rounds=ROUNDS)

    print_comparison(os_results, ab_results)

    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rounds": ROUNDS,
        "opensandbox": os_results,
        "agentbay": ab_results,
    }
    outpath = os.path.join(os.path.dirname(__file__), "comparison_results.json")
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"结果已保存到 {outpath}")


if __name__ == "__main__":
    main()
