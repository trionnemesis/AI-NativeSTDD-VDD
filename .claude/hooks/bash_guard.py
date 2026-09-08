#!/usr/bin/env python3
# Why: prevent common Bash writes from bypassing configured SPEC/RED paths,
# and common Bash reads from bypassing the read-side isolation guard.
# Shell 是開放式的，pattern 比對只擋得住常見寫法；真正的隔離仍靠 role separation。
import json
import re
import sys

from path_policy import (
    IMPLEMENTATION_PHASES,
    PolicyError,
    load_policy,
    project_root,
    read_phase,
)

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

try:
    policy = load_policy()
    root = project_root()
    phase = read_phase(root)
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)

patterns = []
governed_roots = dict.fromkeys(
    [*policy["implementation_roots"], *policy["protected_spec_roots"]]
)
for governed_root in governed_roots:
    relative = re.escape(governed_root)
    absolute = re.escape((root / governed_root).as_posix())
    target = rf"[\"']?(?:(?:\./)?{relative}|{absolute})/"
    patterns.extend(
        [
            (rf">\s*{target}", f"重導向寫入 {governed_root}/"),
            (rf"\btee\s+{target}", f"tee 寫入 {governed_root}/"),
            (rf"\bsed\s+-i.*{target}", f"sed -i 修改 {governed_root}/"),
            (rf"\bcat\s+>.*{target}", f"cat 寫入 {governed_root}/"),
            (rf"\becho\s+.*>\s*{target}", f"echo 寫入 {governed_root}/"),
            (rf"\bcp\s+.*\s+{target}", f"cp 到 {governed_root}/"),
            (rf"\bmv\s+.*\s+{target}", f"mv 到 {governed_root}/"),
        ]
    )

# read-side isolation：與 read_isolation_guard.py 用同一組 phase 定義，
# 擋掉最常見的「用 Bash 讀對側」寫法。
READ_COMMANDS = ("cat", "head", "tail", "less", "more", "bat", "nl", "od", "xxd", "strings")
if phase in IMPLEMENTATION_PHASES:
    forbidden_roots, forbidden_side = policy["test_roots"], "測試"
else:
    forbidden_roots, forbidden_side = policy["implementation_roots"], "實作"

for forbidden_root in dict.fromkeys(forbidden_roots):
    relative = re.escape(forbidden_root)
    absolute = re.escape((root / forbidden_root).as_posix())
    target = rf"[\"']?(?:(?:\./)?{relative}|{absolute})/"
    for reader in READ_COMMANDS:
        patterns.append(
            (
                rf"\b{reader}\s+(?:-\S+\s+|\d+\s+)*{target}",
                f"{reader} 讀取 {forbidden_root}/（{forbidden_side}側）",
            )
        )
    patterns.extend(
        [
            (
                rf"\b(?:grep|rg|ag)\b[^|;&]*\s{target}",
                f"grep/rg 讀取 {forbidden_root}/（{forbidden_side}側）",
            ),
            (
                rf"\bsed\s+-n[^|;&]*\s{target}",
                f"sed -n 讀取 {forbidden_root}/（{forbidden_side}側）",
            ),
            (
                rf"\bawk\b[^|;&]*\s{target}",
                f"awk 讀取 {forbidden_root}/（{forbidden_side}側）",
            ),
        ]
    )

violations = [label for pattern, label in patterns if re.search(pattern, command)]
if violations:
    print(
        "BLOCKED [GATE:SPEC/RED/BASH]: 偵測到透過 Bash 繞過 gate 的嘗試。\n"
        f"  Violations: {', '.join(violations)}\n"
        f"  phase: {phase!r}\n"
        "  寫入請改用 Edit／Write tool，讓 configured hook 正確觸發；\n"
        "  讀取對側受 GATE:RED agent_isolation_enforced 限制，不得以 Bash 繞過。",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
