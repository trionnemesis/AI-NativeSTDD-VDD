#!/usr/bin/env python3
# Why: UserPromptSubmit hook 的 stdout 會注入 context，
# 可把當前 .vdd/phase 狀態和 spec diff 預先內聯，減少 agent 遺漏。
import json
import subprocess
import sys

from path_policy import PolicyError, load_policy, project_root

data = json.load(sys.stdin)

try:
    policy = load_policy()
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)

output_lines = []
root = project_root()

# 注入當前 .vdd/phase 狀態
phase_file = root / ".vdd" / "phase"
if phase_file.exists():
    phase = phase_file.read_text().strip()
    output_lines.append(f"[STDD×VDD] Current gate phase: {phase}")

# 注入 admit queue（若有待處理項目）
admit_queue = root / ".vdd" / "admit-queue"
if admit_queue.exists() and admit_queue.stat().st_size > 0:
    items = admit_queue.read_text().strip().split("\n")
    if items:
        output_lines.append(f"[STDD×VDD] Pending ADMIT items: {', '.join(items[:3])}")

# 注入最近 spec 變更摘要（若有 git）
try:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", *policy["spec_change_paths"]],
        capture_output=True, text=True, errors="replace", timeout=3, cwd=root,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        changed = result.stdout.strip().split("\n")
        output_lines.append(f"[STDD×VDD] Modified spec files: {', '.join(changed[:5])}")
except (OSError, subprocess.SubprocessError) as exc:
    print(f"[STDD×VDD] spec diff skipped: {exc}", file=sys.stderr)

if output_lines:
    print("\n".join(output_lines))

sys.exit(0)
