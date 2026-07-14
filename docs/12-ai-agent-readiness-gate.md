# 12 · AI Agent 就緒閘門（AI Agent Readiness Gate）

> **Authority boundary**：本頁與 [`setup/AGENT_SETUP_PROTOCOL.md`](../setup/AGENT_SETUP_PROTOCOL.md) 提供 human-readable readiness guidance。Notion root、07、21、24 仍是 canonical contracts；只有 Confirm Mode 的實測結果才能宣稱 target environment 已 enforcement。

---

## 概述

AI Agent Readiness Gate 是在把任何任務分派給 AI agent 執行之前，確認環境已正確設定的前置檢查機制。

這等同於 Configure Mode 的 7 phase 驗證序列（P0–P6），但以 agent 視角來描述。

## MCR:2026:004 authority preflight

在 hooks 或 `.vdd/phase` 檢查之前，先確認：

```bash
test -f governance/manifest.yaml
test -d governance/gates
test -d governance/profiles
test -f governance/gates/vdd.yaml
test -f governance/gates/deploy.yaml
```

讀取 `governance/manifest.yaml` 的 authority state，並依任務載入 System／Change Profile、Evidence 與 Release contracts。`SHADOW_NON_AUTHORITATIVE` 表示 Notion 仍為 canonical，不能因本機檔案存在就宣稱 cutover 或完整 runtime enforcement。

---

## Configure Mode 完整清單

### P0：地基驗證

```bash
# 確認 managed-settings.json 存在（macOS）
ls "/Library/Application Support/ClaudeCode/managed-settings.json"

# 確認內容正確
cat "/Library/Application Support/ClaudeCode/managed-settings.json" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  assert d.get('allowManagedPermissionRulesOnly') == True, 'managed permission rules missing'; \
  assert 'allowManagedHooksOnly' not in d, 'project hooks are disabled'; \
  assert d.get('permissions',{}).get('defaultMode') == 'plan', 'defaultMode != plan'; \
  print('P0: OK')"
```

預期輸出：`P0: OK`

### P1：Path policy 與治理目錄驗證

```bash
# 完整 policy schema/path 驗證；不能只跑 json.tool
python3 .claude/hooks/path_policy.py
for dir in .vdd .claude/hooks; do
  [ -d "$dir" ] && echo "OK: $dir" || echo "MISSING: $dir"
done

# phase 檔案
cat .vdd/phase
```

### P2：Hook Scripts 驗證

```bash
# 所有 hook 檔案存在
for hook in pre_impl_gate bash_guard green_gate test_weakening_guard \
            inject_spec reinject_rules path_policy; do
  [ -f ".claude/hooks/${hook}.py" ] && echo "OK: $hook" || echo "MISSING: $hook"
done

# 語法驗證
python3 -m py_compile .claude/hooks/pre_impl_gate.py && echo "syntax: OK"
```

### P3：Hook 註冊驗證

```bash
# Runtime hooks 由 project settings 註冊。
python3 -c "
import json
settings = json.load(open('.claude/settings.json'))
for event in ['PreToolUse', 'Stop', 'UserPromptSubmit']:
    assert event in settings['hooks'], f'{event} missing'
print('P3: OK')
"
```

### P4：RED verifier 驗證

```bash
test -f .claude/agents/red-verifier.md
```

### P5：GREEN command 環境驗證

```bash
# RED/GREEN runtime 的固定工具
for pkg in pytest ruff mutmut; do
  python3 -c "import $pkg" 2>/dev/null && echo "OK: $pkg" || echo "MISSING: $pkg"
done

# 特殊：pytest-cov
python3 -c "import pytest_cov" 2>/dev/null && echo "OK: pytest-cov" || echo "MISSING: pytest-cov"
```

### P6：First-Run 功能驗證（Smoke Test）

```bash
# init.sh 會以 implementation_roots[0]/test.py 模擬 GATE:SPEC 觸發。
# custom layout example：
bash setup/init.sh /tmp/stdd-test ./my-path-policy.json
# 預期 P6: PASS，且輸出顯示實際 configured root
```

---

## Confirm Mode 快速清單（YAML 格式）

Agent 在 Confirm Mode 中讀取此清單：

```yaml
confirm_mode:
  - id: P0
    check: "managed settings 保留 permission 底線且未禁用 project hooks"
    command: "python3 -c \"import json; d=json.load(open('/Library/Application Support/ClaudeCode/managed-settings.json')); assert d.get('allowManagedPermissionRulesOnly') is True and 'allowManagedHooksOnly' not in d\""
    pass_condition: "machine permissions 存在，project hooks 可執行"

  - id: P1
    check: ".vdd/path-policy.json 有效，治理目錄完整"
    command: "python3 .claude/hooks/path_policy.py && ls .vdd/ .claude/hooks/"
    pass_condition: "policy schema/path contract 有效且必要治理目錄存在"

  - id: P2
    check: "6 個 hook entrypoints 與 path_policy.py 存在於 .claude/hooks/"
    command: "ls .claude/hooks/"
    pass_condition: "7 個 .py 檔案存在"

  - id: P3
    check: "project settings 註冊 runtime hooks"
    command: "python3 -c \"import json; h=json.load(open('.claude/settings.json'))['hooks']; assert all(e in h for e in ['PreToolUse','Stop','UserPromptSubmit']); print('P3: OK')\""
    pass_condition: "project hooks 包含 PreToolUse、Stop、UserPromptSubmit"

  - id: P4
    check: "red-verifier subagent 存在"
    command: "test -f .claude/agents/red-verifier.md"
    pass_condition: "RED verifier 可委派"

  - id: P5
    check: "fixed RED/GREEN toolchain 可用"
    command: "python3 -I -m pytest --version && python3 -I -m ruff --version"
    pass_condition: "pytest 與 ruff 可執行"

  - id: P6
    check: "pre_impl_gate.py smoke test：INIT phase 應 block configured implementation root 寫入"
    command: "bash setup/init.sh /tmp/stdd-readiness-smoke"
    pass_condition: "exit code = 2"
```

---

## 部分失敗的處理

| 失敗項目 | 嚴重性 | 處理方式 |
|---------|--------|---------|
| P0 失敗 | **Critical** | 停止，人工安裝 managed settings |
| P1 policy／治理目錄缺失 | High | 以 init.sh 安裝 default 或指定 custom policy |
| P2 hook 缺失 | **Critical** | 停止，從模板複製 |
| P3 project hook 缺失 | **Critical** | 停止，重裝 project settings/hooks |
| P4 RED verifier 缺失 | **Critical** | 停止，從 template 複製 subagent |
| P5 command 缺失 | High | 安裝固定 pytest/ruff verification toolchain |
| P6 smoke test 失敗 | **Critical** | 停止，hook 腳本可能損壞 |

---

## 自動修復腳本

```bash
# 以 init.sh 修復治理檔案；既有 custom layout 不會被覆寫
#!/bin/bash
set -e
bash ../AI-NativeSTDD-VDD/setup/init.sh . .vdd/path-policy.json
```

---

*本章對應 Notion 頁面 12 · AI Agent 就緒閘門*
