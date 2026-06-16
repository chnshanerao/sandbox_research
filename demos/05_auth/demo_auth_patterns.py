#!/usr/bin/env python3
"""
Demo 05: Agent 安全层 — Auth & 工具授权模式
============================================
演示 AI Agent 基础设施中的安全层：
- API Key 安全管理
- 工具调用授权策略（白名单 / 黑名单 / 参数校验）
- 速率限制
- 审计日志

对应基础设施栈：安全层 / Auth & Gateway
参考产品：Arcade.dev ($60M A轮), Okta Agent Gateway, 蚂蚁 ASL
"""
import json
import time
import hashlib
import hmac
from collections import defaultdict
from datetime import datetime


# ══════════════════════════════════════════════════════════════════
# 1. API Key 安全管理
# ══════════════════════════════════════════════════════════════════

class SecureKeyStore:
    """安全的 API Key 管理 — 永远不明文存储/日志输出"""

    def __init__(self):
        self._keys = {}

    def store(self, name: str, key: str):
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        self._keys[name] = {
            "key": key,
            "hash": key_hash,
            "masked": key[:4] + "****" + key[-4:],
            "created_at": datetime.now().isoformat(),
        }

    def get(self, name: str) -> str:
        return self._keys[name]["key"]

    def display(self, name: str) -> str:
        return self._keys[name]["masked"]

    def verify(self, name: str, provided_key: str) -> bool:
        stored_hash = self._keys[name]["hash"]
        provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()[:16]
        return hmac.compare_digest(stored_hash, provided_hash)


# ══════════════════════════════════════════════════════════════════
# 2. 工具授权策略
# ══════════════════════════════════════════════════════════════════

class ToolAuthPolicy:
    """Agent 工具调用的授权策略引擎"""

    def __init__(self):
        self.allowed_tools = set()
        self.denied_tools = set()
        self.path_restrictions = []
        self.rate_limits = {}
        self._call_counts = defaultdict(list)

    def allow(self, *tool_names):
        self.allowed_tools.update(tool_names)

    def deny(self, *tool_names):
        self.denied_tools.update(tool_names)

    def restrict_paths(self, allowed_prefixes: list[str]):
        self.path_restrictions = allowed_prefixes

    def set_rate_limit(self, tool_name: str, max_per_minute: int):
        self.rate_limits[tool_name] = max_per_minute

    def check(self, tool_name: str, arguments: dict) -> tuple[bool, str]:
        if tool_name in self.denied_tools:
            return False, f"工具 '{tool_name}' 在黑名单中"

        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False, f"工具 '{tool_name}' 不在白名单中"

        if tool_name in self.rate_limits:
            now = time.time()
            self._call_counts[tool_name] = [
                t for t in self._call_counts[tool_name] if now - t < 60
            ]
            if len(self._call_counts[tool_name]) >= self.rate_limits[tool_name]:
                return False, f"工具 '{tool_name}' 超过速率限制 ({self.rate_limits[tool_name]}/min)"
            self._call_counts[tool_name].append(now)

        if self.path_restrictions:
            for key in ("path", "file_path", "directory"):
                if key in arguments:
                    path = arguments[key]
                    if not any(path.startswith(p) for p in self.path_restrictions):
                        return False, f"路径 '{path}' 不在允许范围内 (允许: {self.path_restrictions})"

        return True, "授权通过"


# ══════════════════════════════════════════════════════════════════
# 3. 审计日志
# ══════════════════════════════════════════════════════════════════

class AuditLogger:
    """结构化审计日志 — 记录每次工具调用"""

    def __init__(self):
        self.logs = []

    def log(self, tool_name: str, arguments: dict, allowed: bool, reason: str, duration_ms: float = 0):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": {k: str(v)[:50] for k, v in arguments.items()},
            "allowed": allowed,
            "reason": reason,
            "duration_ms": round(duration_ms, 1),
        }
        self.logs.append(entry)

    def summary(self):
        total = len(self.logs)
        allowed = sum(1 for l in self.logs if l["allowed"])
        denied = total - allowed
        return {"total": total, "allowed": allowed, "denied": denied}


# ══════════════════════════════════════════════════════════════════
# 4. 安全网关 — 组合以上组件
# ══════════════════════════════════════════════════════════════════

class AgentSecurityGateway:
    """Agent 安全网关 — 在 Agent 和工具之间的拦截层"""

    def __init__(self, policy: ToolAuthPolicy, audit: AuditLogger):
        self.policy = policy
        self.audit = audit
        self.tools = {}

    def register_tool(self, name: str, func):
        self.tools[name] = func

    def execute(self, tool_name: str, arguments: dict) -> dict:
        allowed, reason = self.policy.check(tool_name, arguments)

        if not allowed:
            self.audit.log(tool_name, arguments, False, reason)
            return {"status": "DENIED", "reason": reason}

        if tool_name not in self.tools:
            self.audit.log(tool_name, arguments, False, "工具未注册")
            return {"status": "ERROR", "reason": f"未知工具: {tool_name}"}

        t0 = time.time()
        try:
            result = self.tools[tool_name](**arguments)
            duration = (time.time() - t0) * 1000
            self.audit.log(tool_name, arguments, True, "执行成功", duration)
            return {"status": "OK", "result": result, "duration_ms": round(duration, 1)}
        except Exception as e:
            duration = (time.time() - t0) * 1000
            self.audit.log(tool_name, arguments, True, f"执行异常: {e}", duration)
            return {"status": "ERROR", "reason": str(e)}


# ══════════════════════════════════════════════════════════════════
# Demo 工具函数
# ══════════════════════════════════════════════════════════════════

def calculator(expression: str) -> str:
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        raise ValueError(f"不安全的表达式: {expression}")
    return str(eval(expression))

def read_file(path: str) -> str:
    import os
    if not os.path.exists(path):
        return f"文件不存在: {path}"
    with open(path) as f:
        return f.read()[:500]

def execute_shell(command: str) -> str:
    return f"[模拟] 执行命令: {command}"

def delete_file(path: str) -> str:
    return f"[模拟] 删除文件: {path}"


# ══════════════════════════════════════════════════════════════════
# 运行演示
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Demo 05: Agent 安全层 — Auth & 工具授权")
    print("  对应层: 安全层 / Auth & Gateway")
    print("=" * 70)

    # --- 1. Key 管理 ---
    print("\n[1] API Key 安全管理")
    print("-" * 40)
    store = SecureKeyStore()
    store.store("agentbay", "akm-3d21e663-3224-4cee-ae77-a6c6c7ccb6d7")
    store.store("openai", "sk-proj-abcdefghijklmnop")

    print(f"  AgentBay Key: {store.display('agentbay')}")
    print(f"  OpenAI Key:   {store.display('openai')}")
    print(f"  验证正确Key:  {store.verify('agentbay', 'akm-3d21e663-3224-4cee-ae77-a6c6c7ccb6d7')}")
    print(f"  验证错误Key:  {store.verify('agentbay', 'wrong-key')}")

    # --- 2. 策略配置 ---
    print("\n[2] 工具授权策略配置")
    print("-" * 40)
    policy = ToolAuthPolicy()
    policy.allow("calculator", "read_file", "execute_shell")
    policy.deny("delete_file")
    policy.restrict_paths(["/tmp/", "/home/admin/workspace/"])
    policy.set_rate_limit("execute_shell", max_per_minute=3)

    print(f"  白名单: {sorted(policy.allowed_tools)}")
    print(f"  黑名单: {sorted(policy.denied_tools)}")
    print(f"  路径限制: {policy.path_restrictions}")
    print(f"  速率限制: {policy.rate_limits}")

    # --- 3. 安全网关 ---
    print("\n[3] 安全网关 — 工具调用拦截")
    print("-" * 40)
    audit = AuditLogger()
    gateway = AgentSecurityGateway(policy, audit)
    gateway.register_tool("calculator", calculator)
    gateway.register_tool("read_file", read_file)
    gateway.register_tool("execute_shell", execute_shell)
    gateway.register_tool("delete_file", delete_file)

    test_cases = [
        ("calculator",    {"expression": "15 * 37 + 12"},      "允许: 白名单工具 + 合法参数"),
        ("read_file",     {"path": "/tmp/test.txt"},            "允许: 白名单 + 允许路径"),
        ("read_file",     {"path": "/etc/shadow"},              "拒绝: 路径不在允许范围"),
        ("delete_file",   {"path": "/tmp/important.txt"},       "拒绝: 工具在黑名单中"),
        ("hack_system",   {"target": "root"},                   "拒绝: 工具不在白名单中"),
        ("execute_shell", {"command": "ls /tmp"},               "允许: 第1次调用"),
        ("execute_shell", {"command": "ps aux"},                "允许: 第2次调用"),
        ("execute_shell", {"command": "whoami"},                "允许: 第3次调用"),
        ("execute_shell", {"command": "rm -rf /"},              "拒绝: 超过速率限制 (3/min)"),
    ]

    for tool, args, description in test_cases:
        result = gateway.execute(tool, args)
        status = result["status"]
        icon = "PASS" if status == "OK" else "DENY" if status == "DENIED" else "ERR"
        detail = result.get("result", result.get("reason", ""))
        print(f"  [{icon:4s}] {description}")
        print(f"         {tool}({args}) → {str(detail)[:60]}")

    # --- 4. 审计摘要 ---
    print("\n[4] 审计日志摘要")
    print("-" * 40)
    summary = audit.summary()
    print(f"  总调用: {summary['total']}")
    print(f"  允许:   {summary['allowed']}")
    print(f"  拒绝:   {summary['denied']}")

    print("\n  详细日志:")
    for entry in audit.logs:
        icon = "OK" if entry["allowed"] else "NO"
        print(f"    [{icon}] {entry['tool']:15s} | {entry['reason'][:40]}")

    # --- 5. 架构说明 ---
    print("\n" + "=" * 70)
    print("  架构示意")
    print("=" * 70)
    print("""
  Agent (LLM)                安全网关                    工具
  ┌────────┐    tool_call    ┌──────────────┐           ┌──────────┐
  │        │ ──────────────→ │ 1. 白/黑名单  │ ────OK──→ │calculator│
  │  GPT-4 │                 │ 2. 路径校验   │           │read_file │
  │ Claude │ ←────result──── │ 3. 速率限制   │ ←result── │shell_exec│
  │        │                 │ 4. 审计日志   │           └──────────┘
  └────────┘                 └──────────────┘
                                   │
                                   ▼ DENY
                             ┌──────────────┐
                             │ 返回拒绝原因  │
                             │ 记录审计日志  │
                             └──────────────┘

  真实产品:
  - Arcade.dev ($60M A轮): 管理 OAuth/Auth，给 Agent 做工具级别授权
  - Okta Agent Gateway: 企业身份 → Agent 身份扩展
  - 蚂蚁 ASL 协议: 跨 Agent 身份验证 + 意图防篡改
""")


if __name__ == "__main__":
    main()
