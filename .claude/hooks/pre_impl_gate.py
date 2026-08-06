#!/usr/bin/env python3
# Why: SPEC Gate + RED Gate 鏈。PreToolUse Edit|Write 觸發。
# 阻擋 protected spec 寫入，或在無 spec / RED evidence 時寫 implementation。
import json
import sys

from path_policy import (
    CONFIG_PATH,
    PolicyError,
    feature_spec_paths,
    implementation_context,
    load_policy,
    path_in_roots,
    project_root,
    red_evidence_path,
    repo_relative_path,
)

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")

try:
    policy = load_policy()
    relative_path = repo_relative_path(path)
    protected_spec = path_in_roots(path, policy["protected_spec_roots"])
    context = implementation_context(path, policy)
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)

if relative_path == CONFIG_PATH.as_posix():
    print(
        f"BLOCKED [PATH POLICY]: {relative_path} 是 protected governance control。\n"
        "  請由人工在 Configure Mode 更新並重跑 readiness checks。",
        file=sys.stderr,
    )
    sys.exit(2)

if protected_spec:
    print(
        f"BLOCKED [GATE:SPEC]: {path} 位於 configured protected spec roots。\n"
        "  Canonical spec 必須經核准的 spec/change workflow 更新。",
        file=sys.stderr,
    )
    sys.exit(2)

if context is None:
    sys.exit(0)

# GATE:SPEC — 確認對應 feature 存在
try:
    specs = feature_spec_paths(policy, context)
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)
try:
    has_spec = any(spec.exists() and spec.stat().st_size > 0 for spec in specs)
except OSError as exc:
    print(f"BLOCKED [GATE:SPEC]: 無法檢查 configured feature spec: {exc}", file=sys.stderr)
    sys.exit(2)
if not has_spec:
    expected = "、".join(str(spec) for spec in specs)
    print(
        f"BLOCKED [GATE:SPEC]: 寫 {path} 前須先補 spec。\n"
        f"  找不到 configured feature spec: {expected}\n"
        f"  請先建立 spec 檔案，再進行實作。",
        file=sys.stderr,
    )
    sys.exit(2)

# GATE:RED — 確認 .vdd/phase 狀態
try:
    phase_file = project_root() / ".vdd" / "phase"
    phase_exists = phase_file.exists()
except (OSError, PolicyError) as exc:
    print(f"BLOCKED [GATE:RED]: 無法檢查治理狀態檔: {exc}", file=sys.stderr)
    sys.exit(2)
if not phase_exists:
    print(
        "BLOCKED [GATE:RED]: .vdd/phase 不存在，無法確認 RED gate。\n"
        "  請先執行 setup/init.sh 或 Configure Mode 建立治理狀態檔。",
        file=sys.stderr
    )
    sys.exit(2)

try:
    phase = phase_file.read_text(encoding="utf-8").strip()
except (OSError, UnicodeError) as exc:
    print(f"BLOCKED [GATE:RED]: 無法讀取 {phase_file}: {exc}", file=sys.stderr)
    sys.exit(2)
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
try:
    red_evidence = red_evidence_path(policy, context)
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)
required_keys = {
    "requirement_id",
    "test_name",
    "baseline_commit_sha",
    "failure_message",
    "failure_location",
    "execution_timestamp",
    "failure_category",
}

try:
    has_red_evidence = red_evidence.exists() and red_evidence.stat().st_size > 0
except OSError as exc:
    print(f"BLOCKED [GATE:RED]: 無法檢查 Red Evidence: {exc}", file=sys.stderr)
    sys.exit(2)
if not has_red_evidence:
    print(
        f"BLOCKED [GATE:RED]: 找不到 Red Evidence: {red_evidence}\n"
        f"  寫 {path} 前必須先存入測試失敗證據。",
        file=sys.stderr
    )
    sys.exit(2)

try:
    evidence = json.loads(red_evidence.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    print(
        f"BLOCKED [GATE:RED]: Red Evidence 不是有效 JSON: {red_evidence}\n"
        f"  {exc}",
        file=sys.stderr
    )
    sys.exit(2)

if not isinstance(evidence, dict):
    print(
        f"BLOCKED [GATE:RED]: Red Evidence 必須是 JSON object: {red_evidence}",
        file=sys.stderr,
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

invalid_values = sorted(
    key
    for key in required_keys
    if not isinstance(evidence.get(key), str) or not evidence[key].strip()
)
if invalid_values:
    print(
        f"BLOCKED [GATE:RED]: Red Evidence 欄位必須是非空字串: {red_evidence}\n"
        f"  Invalid: {', '.join(invalid_values)}",
        file=sys.stderr,
    )
    sys.exit(2)

if evidence["failure_category"].upper() == "ENVIRONMENT_ERROR":
    print(
        f"BLOCKED [GATE:RED]: 環境錯誤不算 RED: {red_evidence}",
        file=sys.stderr
    )
    sys.exit(2)

sys.exit(0)
