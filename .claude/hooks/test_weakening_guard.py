#!/usr/bin/env python3
# Why: 偵測實作 Agent 弱化測試的粗暴 pattern（語意弱化仍需 LLM 判斷）。
# 僅抓確定性可偵測的模式：assert True、pytest.skip、expected value 消失。
import json, sys, pathlib, re

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")

# 只對 test 檔案啟動
if not ("test" in path or "spec" in path.lower()):
    sys.exit(0)

content = pathlib.Path(path).read_text(errors="ignore") if pathlib.Path(path).exists() else ""

weakening_patterns = [
    (r"\bassert\s+True\b", "assert True（無效斷言）"),
    (r"@pytest\.skip", "pytest.skip（測試被跳過）"),
    (r"@unittest\.skip", "unittest.skip（測試被跳過）"),
    (r"\bxfail\b", "xfail（預期失敗標記）"),
    (r"\bpass\s*#.*assert", "pass 替代 assert"),
]

violations = []
for pattern, label in weakening_patterns:
    if re.search(pattern, content):
        violations.append(label)

if violations:
    print(
        f"BLOCKED [GATE:RED invariant]: {path} 疑似測試弱化 pattern:\n"
        f"  {', '.join(violations)}\n"
        f"  禁止弱化/跳過/空斷言測試。",
        file=sys.stderr
    )
    sys.exit(2)

sys.exit(0)
