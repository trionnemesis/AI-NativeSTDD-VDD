#!/usr/bin/env python3
# Why: UserPromptSubmit hook 的 stdout 會注入 context，
# 可把當前 .vdd/phase 狀態和 spec diff 預先內聯，減少 agent 遺漏。
import json, sys, pathlib, subprocess

data = json.load(sys.stdin)

output_lines = []

# 注入當前 .vdd/phase 狀態
phase_file = pathlib.Path(".vdd/phase")
if phase_file.exists():
    phase = phase_file.read_text().strip()
    output_lines.append(f"[STDD×VDD] Current gate phase: {phase}")

# 注入 admit queue（若有待處理項目）
admit_queue = pathlib.Path(".vdd/admit-queue")
if admit_queue.exists() and admit_queue.stat().st_size > 0:
    items = admit_queue.read_text().strip().split("\n")
    if items:
        output_lines.append(f"[STDD×VDD] Pending ADMIT items: {', '.join(items[:3])}")

# 注入最近 spec 變更摘要（若有 git）
try:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", "spec/", "specs/"],
        capture_output=True, text=True, timeout=3
    )
    if result.returncode == 0 and result.stdout.strip():
        changed = result.stdout.strip().split("\n")
        output_lines.append(f"[STDD×VDD] Modified spec files: {', '.join(changed[:5])}")
except Exception:
    pass

if output_lines:
    print("\n".join(output_lines))

sys.exit(0)
