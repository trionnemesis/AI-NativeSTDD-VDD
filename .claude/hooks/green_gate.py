#!/usr/bin/env python3
# Why: GREEN Gate — Stop hook。configured verification commands 全數通過才允許結束。
import json
import subprocess
import sys

from path_policy import PolicyError, load_policy, project_root

data = json.load(sys.stdin)
COMMAND_TIMEOUT_SECONDS = 300

# 防止 Stop hook 遞迴呼叫自己
if data.get("stop_hook_active"):
    sys.exit(0)

def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)


try:
    policy = load_policy()
except PolicyError as exc:
    block(f"[PATH POLICY] {exc}")

commands = [
    [
        sys.executable,
        "-I",
        "-m",
        "pytest",
        *policy["test_roots"],
        "-q",
        "-m",
        "not integration",
    ],
    [sys.executable, "-I", "-m", "ruff", "check", "."],
]
for index, command in enumerate(commands, start=1):
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=project_root(),
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, PolicyError, subprocess.TimeoutExpired) as exc:
        executable = command[0] if command else "<unresolved>"
        block(
            f"[GATE:GREEN] configured command #{index} ({executable}) "
            f"無法執行：{type(exc).__name__}"
        )
    if result.returncode != 0:
        block(
            f"[GATE:GREEN] configured command #{index} 失敗"
            f"（exit={result.returncode}）；請在本機重跑以查看完整輸出。"
        )

# 更新 phase 到 GREEN
phase_file = project_root() / ".vdd" / "phase"
if phase_file.exists():
    try:
        current = phase_file.read_text(encoding="utf-8").strip()
        if current == "RED_VERIFIED":
            phase_file.write_text("GREEN", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        block(f"[GATE:GREEN] 無法更新 phase：{type(exc).__name__}")

sys.exit(0)
