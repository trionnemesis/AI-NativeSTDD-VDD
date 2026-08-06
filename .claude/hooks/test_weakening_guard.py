#!/usr/bin/env python3
# Why: 偵測實作 Agent 弱化測試的粗暴 pattern（語意弱化仍需 LLM 判斷）。
# 僅抓確定性可偵測的模式：assert True、pytest.skip、expected value 消失。
import json
import re
import sys

from path_policy import (
    PolicyError,
    load_policy,
    matches_test_path,
    repository_path,
)

data = json.load(sys.stdin)
tool_input = data.get("tool_input", {})
path = tool_input.get("file_path", "")

try:
    policy = load_policy()
    is_test_path = matches_test_path(path, policy)
    test_path = repository_path(path)
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)

if not is_test_path:
    sys.exit(0)

proposed_content = tool_input.get("content")
if proposed_content is None:
    proposed_content = tool_input.get("new_string")
if proposed_content is None:
    try:
        proposed_content = (
            test_path.read_text(errors="ignore")
            if test_path and test_path.exists()
            else ""
        )
    except OSError as exc:
        print(f"BLOCKED [GATE:RED invariant]: 無法讀取 {path}: {exc}", file=sys.stderr)
        sys.exit(2)

weakening_patterns = [
    (r"\bassert\s+True\b", "assert True（無效斷言）"),
    (r"@pytest\.skip", "pytest.skip（測試被跳過）"),
    (r"@unittest\.skip", "unittest.skip（測試被跳過）"),
    (r"\bxfail\b", "xfail（預期失敗標記）"),
    (r"\bpass\s*#.*assert", "pass 替代 assert"),
]

violations = []
for pattern, label in weakening_patterns:
    if re.search(pattern, proposed_content):
        violations.append(label)

old_string = tool_input.get("old_string", "")
new_string = tool_input.get("new_string", "")
if re.search(r"\bassert\b", old_string) and not re.search(r"\bassert\b", new_string):
    violations.append("移除既有 assert")

if violations:
    print(
        f"BLOCKED [GATE:RED invariant]: {path} 疑似測試弱化 pattern:\n"
        f"  {', '.join(violations)}\n"
        f"  禁止弱化/跳過/空斷言測試。",
        file=sys.stderr
    )
    sys.exit(2)

sys.exit(0)
