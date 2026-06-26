# 12 · AI Agent 就緒閘門（AI Agent Readiness Gate）

---

## 概述

AI Agent Readiness Gate 是在把任何任務分派給 AI agent 執行之前，確認環境已正確設定的前置檢查機制。

這等同於 Configure Mode 的 7 phase 驗證序列（P0–P6），但以 agent 視角來描述。

---

## Configure Mode 完整清單

### P0：地基驗證

```bash
# 確認 managed-settings.json 存在（macOS）
ls "/Library/Application Support/ClaudeCode/managed-settings.json"

# 確認內容正確
cat "/Library/Application Support/ClaudeCode/managed-settings.json" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  assert d.get('allowManagedHooksOnly') == True, 'allowManagedHooksOnly missing'; \
  assert d.get('permissions',{}).get('defaultMode') == 'plan', 'defaultMode != plan'; \
  print('P0: OK')"
```

預期輸出：`P0: OK`

### P1：目錄結構驗證

```bash
# 必要目錄
for dir in specs/domain specs/features specs/contracts/api specs/contracts/ui \
           specs/quality specs/decisions specs/traceability \
           .vdd/red .claude/hooks .claude/agents; do
  [ -d "$dir" ] && echo "OK: $dir" || echo "MISSING: $dir"
done

# phase 檔案
cat .vdd/phase
```

### P2：Hook Scripts 驗證

```bash
# 所有 hook 檔案存在
for hook in pre_impl_gate bash_guard green_gate test_weakening_guard \
            inject_spec reinject_rules; do
  [ -f ".claude/hooks/${hook}.py" ] && echo "OK: $hook" || echo "MISSING: $hook"
done

# 語法驗證
python3 -m py_compile .claude/hooks/pre_impl_gate.py && echo "syntax: OK"
```

### P3：Hook 註冊驗證

```bash
# settings.json 存在且有 hooks 定義
python3 -c "
import json
d = json.load(open('.claude/settings.json'))
assert 'hooks' in d
for event in ['PreToolUse', 'Stop', 'UserPromptSubmit']:
    assert event in d['hooks'], f'{event} missing'
print('P3: OK')
"
```

### P4：Subagent 驗證

```bash
# red-verifier 存在
[ -f ".claude/agents/red-verifier.md" ] && echo "P4: OK" || echo "P4: MISSING"

# 確認 frontmatter 正確
python3 -c "
content = open('.claude/agents/red-verifier.md').read()
assert 'disallowedTools:' in content
assert 'Write' in content
assert 'Edit' in content
print('P4 subagent: OK')
"
```

### P5：Python 環境驗證

```bash
# 必要套件
for pkg in pytest ruff mutmut; do
  python3 -c "import $pkg" 2>/dev/null && echo "OK: $pkg" || echo "MISSING: $pkg"
done

# 特殊：pytest-cov
python3 -c "import pytest_cov" 2>/dev/null && echo "OK: pytest-cov" || echo "MISSING: pytest-cov"
```

### P6：First-Run 功能驗證（Smoke Test）

```bash
# 模擬 GATE:SPEC 觸發（應被 block）
# 在 .vdd/phase = INIT 的狀態下，嘗試寫 src/ 應被 hook 阻擋

# 建立測試環境
mkdir -p /tmp/stdd-test/src
echo "INIT" > /tmp/stdd-test/.vdd/phase
cp .claude/hooks/pre_impl_gate.py /tmp/stdd-test/

# 模擬 hook 輸入（Edit tool 到 src/test.py）
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/test.py"}}' | \
  python3 .claude/hooks/pre_impl_gate.py 2>&1; echo "exit: $?"
# 預期輸出: BLOCKED: ... 且 exit code = 2
```

---

## Confirm Mode 快速清單（YAML 格式）

Agent 在 Confirm Mode 中讀取此清單：

```yaml
confirm_mode:
  - id: P0
    check: "managed-settings.json 存在且 allowManagedHooksOnly = true"
    command: "cat '/Library/Application Support/ClaudeCode/managed-settings.json'"
    pass_condition: "allowManagedHooksOnly == true"

  - id: P1
    check: "specs/ 和 .vdd/ 目錄結構完整"
    command: "ls specs/ .vdd/"
    pass_condition: "所有必要目錄存在"

  - id: P2
    check: "6 個 hook scripts 存在於 .claude/hooks/"
    command: "ls .claude/hooks/"
    pass_condition: "6 個 .py 檔案存在"

  - id: P3
    check: ".claude/settings.json 有 PreToolUse + Stop 註冊"
    command: "python3 -c \"import json; print(json.load(open('.claude/settings.json'))['hooks'].keys())\""
    pass_condition: "包含 PreToolUse 和 Stop"

  - id: P4
    check: "red-verifier.md 存在於 .claude/agents/"
    command: "ls .claude/agents/"
    pass_condition: "red-verifier.md 存在"

  - id: P5
    check: "pytest, ruff, mutmut 已安裝"
    command: "python3 -m pytest --version && ruff --version && mutmut --version"
    pass_condition: "三個命令都成功"

  - id: P6
    check: "pre_impl_gate.py smoke test：INIT phase 應 block src/ 寫入"
    command: "見 P6 說明"
    pass_condition: "exit code = 2"
```

---

## 部分失敗的處理

| 失敗項目 | 嚴重性 | 處理方式 |
|---------|--------|---------|
| P0 失敗 | **Critical** | 停止，人工安裝 managed-settings.json |
| P1 目錄缺失 | High | 自動建立目錄 |
| P2 hook 缺失 | **Critical** | 停止，從模板複製 |
| P3 settings 缺失 | **Critical** | 停止，從模板複製 |
| P4 subagent 缺失 | Medium | 自動複製，但 RED Gate 降級到 manual |
| P5 套件缺失 | High | 自動執行 pip install |
| P6 smoke test 失敗 | **Critical** | 停止，hook 腳本可能損壞 |

---

## 自動修復腳本

```bash
# scripts/repair.sh — 嘗試自動修復 P1/P4/P5
#!/bin/bash
set -e

# P1: 建目錄
mkdir -p specs/{domain,features,contracts/{api,ui},quality,decisions,traceability}
mkdir -p .vdd/red
[ -f .vdd/phase ] || echo "INIT" > .vdd/phase

# P2: 若有模板，複製 hooks
if [ -d "../AI-NativeSTDD-VDD/.claude/hooks" ]; then
  mkdir -p .claude/hooks
  cp ../AI-NativeSTDD-VDD/.claude/hooks/*.py .claude/hooks/
  echo "P2: hooks copied"
fi

# P5: 安裝套件
pip install -q pytest pytest-cov ruff mutmut
echo "P5: packages installed"
```

---

*本章對應 Notion 頁面 12 · AI Agent 就緒閘門*
