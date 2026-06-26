#!/usr/bin/env python3
# Why: GREEN Gate — Stop hook。所有測試通過 + lint clean 才允許 session 結束。
import json, sys, subprocess, shutil

data = json.load(sys.stdin)

# 防止 Stop hook 遞迴呼叫自己
if data.get("stop_hook_active"):
    sys.exit(0)

def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)


# 執行測試（排除 integration tests，避免環境依賴）
r = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q", "-m", "not integration"],
    capture_output=True, text=True
)

if not shutil.which("ruff"):
    block("[GATE:GREEN] 未通過：找不到 ruff。請先安裝 P5 依賴或修正 PATH。")

# 執行 lint
lint = subprocess.run(
    ["ruff", "check", "."],
    capture_output=True, text=True
)

if r.returncode != 0 or lint.returncode != 0:
    combined = (r.stdout + r.stderr + lint.stdout + lint.stderr)[-3000:]
    block(
        f"[GATE:GREEN] 未通過，不可結束 session。請繼續修復。\n\n"
        f"{combined}"
    )

# 更新 phase 到 GREEN
import pathlib
phase_file = pathlib.Path(".vdd/phase")
if phase_file.exists():
    current = phase_file.read_text().strip()
    if current == "RED_VERIFIED":
        phase_file.write_text("GREEN")

sys.exit(0)
