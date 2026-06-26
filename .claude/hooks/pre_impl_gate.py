#!/usr/bin/env python3
# Why: SPEC Gate + RED Gate 鏈。PreToolUse Edit|Write 觸發。
# 阻擋在無 spec、RED 未驗證或缺 Red Evidence 的情況下寫 src/ 實作。
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
if not phase_file.exists():
    print(
        "BLOCKED [GATE:RED]: .vdd/phase 不存在，無法確認 RED gate。\n"
        "  請先執行 setup/init.sh 或 Configure Mode 建立治理狀態檔。",
        file=sys.stderr
    )
    sys.exit(2)

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

# GATE:RED — 確認 Red Evidence 存在且可機器解析
red_evidence = pathlib.Path(".vdd/red") / f"{module}.json"
required_keys = {
    "requirement_id",
    "test_name",
    "baseline_commit_sha",
    "failure_message",
    "failure_location",
    "execution_timestamp",
    "failure_category",
}

if not red_evidence.exists() or red_evidence.stat().st_size == 0:
    print(
        f"BLOCKED [GATE:RED]: 找不到 Red Evidence: {red_evidence}\n"
        f"  寫 {path} 前必須先存入測試失敗證據。",
        file=sys.stderr
    )
    sys.exit(2)

try:
    evidence = json.loads(red_evidence.read_text())
except json.JSONDecodeError as exc:
    print(
        f"BLOCKED [GATE:RED]: Red Evidence 不是有效 JSON: {red_evidence}\n"
        f"  {exc}",
        file=sys.stderr
    )
    sys.exit(2)

missing = sorted(required_keys - evidence.keys())
if missing:
    print(
        f"BLOCKED [GATE:RED]: Red Evidence 欄位不足: {red_evidence}\n"
        f"  Missing: {', '.join(missing)}",
        file=sys.stderr
    )
    sys.exit(2)

if str(evidence.get("failure_category", "")).upper() == "ENVIRONMENT_ERROR":
    print(
        f"BLOCKED [GATE:RED]: 環境錯誤不算 RED: {red_evidence}",
        file=sys.stderr
    )
    sys.exit(2)

sys.exit(0)
