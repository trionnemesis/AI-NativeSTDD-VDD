#!/usr/bin/env python3
# Why: SPEC Gate + RED Gate 鏈。PreToolUse Edit|Write 觸發。
# 阻擋在無 spec 或 RED 未驗證的情況下寫 src/ 實作。
import json, sys, pathlib

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")

# 只對 src/ 目錄下的實作檔生效
if "/src/" not in path and not path.startswith("src/"):
    sys.exit(0)

# GATE:SPEC — 確認對應 feature 存在
module = pathlib.Path(path).stem
spec = pathlib.Path("specs/features") / f"{module}.feature"
# 也嘗試舊路徑格式
spec_old = pathlib.Path("spec/features") / f"{module}.feature"

if not ((spec.exists() and spec.stat().st_size > 0) or
        (spec_old.exists() and spec_old.stat().st_size > 0)):
    print(
        f"BLOCKED [GATE:SPEC]: 寫 {path} 前須先補 spec。\n"
        f"  找不到: {spec} （或 {spec_old}）\n"
        f"  請先建立 spec 檔案，再進行實作。",
        file=sys.stderr
    )
    sys.exit(2)

# GATE:RED — 確認 .vdd/phase 狀態
phase_file = pathlib.Path(".vdd/phase")
if phase_file.exists():
    phase = phase_file.read_text().strip()
    if phase not in ("RED_VERIFIED", "GREEN"):
        print(
            f"BLOCKED [GATE:RED]: RED gate 未通過（phase={phase!r}）\n"
            f"  目前狀態不允許寫實作。\n"
            f"  請委派 red-verifier subagent 執行 RED 驗證，"
            f"確認測試失敗後再繼續。",
            file=sys.stderr
        )
        sys.exit(2)

sys.exit(0)
