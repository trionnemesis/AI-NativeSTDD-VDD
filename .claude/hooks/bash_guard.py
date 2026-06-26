#!/usr/bin/env python3
# Why: 防止 agent 用 Bash 繞過 PreToolUse Edit/Write 的 hook 限制。
# 偵測 Bash 命令中直接寫入 src/ 的 pattern。
import json, sys, re, pathlib

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

# 偵測 Bash 寫入 src/ 的常見模式
bypass_patterns = [
    (r">\s*src/", "重導向寫入 src/"),
    (r"tee\s+src/", "tee 寫入 src/"),
    (r"sed\s+-i.*src/", "sed -i 修改 src/"),
    (r"cat\s+>.*src/", "cat 寫入 src/"),
    (r"echo\s+.*>\s*src/", "echo 寫入 src/"),
    (r"cp\s+.*\s+src/", "cp 到 src/"),
    (r"mv\s+.*\s+src/", "mv 到 src/"),
]

violations = []
for pattern, label in bypass_patterns:
    if re.search(pattern, command):
        violations.append(label)

if violations:
    # 同樣檢查 phase（與 pre_impl_gate.py 一致）
    phase_file = pathlib.Path(".vdd/phase")
    if phase_file.exists():
        phase = phase_file.read_text().strip()
        if phase not in ("RED_VERIFIED", "GREEN"):
            print(
                f"BLOCKED [GATE:RED/BASH]: 偵測到透過 Bash 繞過 gate 的嘗試。\n"
                f"  Violations: {', '.join(violations)}\n"
                f"  目前 phase={phase!r}，不允許寫 src/。\n"
                f"  請使用 Edit 或 Write tool，讓 hook 正確觸發。",
                file=sys.stderr
            )
            sys.exit(2)

sys.exit(0)
