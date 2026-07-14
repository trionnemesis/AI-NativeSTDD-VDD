# 10 · Claude Code 具體實作（Implementation）

> **Status: Implementation/reference snapshot.** 本頁的 Claude Code capability 與 hook behavior 必須在 target environment 以 Confirm Mode 重驗；Notion canonical contracts 與 `governance/manifest.yaml` 的 authority state 優先。

---

## 概述

本章說明在 Claude Code CLI 中實作 STDD×VDD 治理層的具體技術細節，包含 7 個設定階段（P0–P6）。

---

## 7 Phase 設定序列（P0–P6）

### P0：地基（managed-settings.json）

**位置（macOS）**：`/Library/Application Support/ClaudeCode/managed-settings.json`  
**需要管理員權限**  
**優先權**：Precedence 1，不可被任何其他設定覆蓋

```json
{
  "permissions": {
    "defaultMode": "plan",
    "deny": [
      "Edit(./.git/**)",
      "Edit(./.claude/hooks/**)",
      "Bash(curl *)",
      "Bash(wget *)"
    ]
  },
  "disableAutoMode": "disable",
  "disableBypassPermissionsMode": "disable",
  "allowManagedPermissionRulesOnly": true,
  "env": {
    "CLAUDE_CODE_STOP_HOOK_BLOCK_CAP": "20"
  }
}
```

完整設定見 [managed-settings template](../setup/templates/managed-settings.json)。Machine-wide 層只保留共通 permission 底線；不設定 `allowManagedHooksOnly`，避免阻擋 project-local、path-aware hooks 與 `red-verifier`。

**關鍵說明**：
- `defaultMode: "plan"`：所有操作預設需要計畫確認
- configured protected spec roots 由 project `pre_impl_gate.py` 讀取 target policy，避免 machine policy 綁死 spec folder
- `allowManagedPermissionRulesOnly`：共通 permissions 仍由管理員控制
- `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP: 20`：Stop hook 最多 block 20 次，防無限循環

---

### P1：目錄結構初始化

```bash
# Compatibility layout
bash setup/init.sh <target-project-dir>

# Custom layout：第二參數提供 project-local policy
bash setup/init.sh <target-project-dir> <path-policy-json>
```

Policy 寫入 `<target>/.vdd/path-policy.json`。若未提供，init 安裝 `setup/templates/path-policy.json` 並建立既有 `specs/` layout；若提供 custom policy，init 不會合成 `src/`、`specs/` 或 `tests/`。

| Policy key | Contract |
|---|---|
| `implementation_roots` | 受 SPEC/RED gate 管理的 implementation roots |
| `feature_spec_templates` | 由 implementation context 解析 feature spec |
| `protected_spec_roots` | 禁止 agent 直接修改的 canonical spec roots |
| `red_evidence_template` | Red Evidence path template |
| `test_file_patterns` | deterministic test weakening globs；defaults 保留 legacy `test`／`spec` matching semantics |
| `test_roots` | GREEN pytest 與 RED test-path containment 使用的 test roots |
| `spec_change_paths` | spec diff injection paths |

Policy 是 partial override：省略的 key 使用 compatibility default。它只描述 repository path/layout，不接受 executable 或 shell command。格式或 path containment 錯誤必須 loud fail。

---

### P2：Hook Scripts 安裝

`.claude/hooks/*.py` 是 versioned project runtime：

```bash
cp <stdd-vdd-repo>/.claude/hooks/*.py .claude/hooks/
chmod +x .claude/hooks/*.py
```

Hook 功能對照：

| 檔案 | 觸發時機 | 功能 |
|------|---------|------|
| `pre_impl_gate.py` | PreToolUse Edit/Write | SPEC + RED Gate 檢查 |
| `bash_guard.py` | PreToolUse Bash | 防止 Bash 繞過 gate |
| `green_gate.py` | Stop | GREEN Gate，阻擋不完整結束 |
| `test_weakening_guard.py` | PreToolUse Edit/Write | mutation 前偵測測試弱化／assert removal |
| `inject_spec.py` | UserPromptSubmit | 注入 .vdd/phase 狀態 |
| `reinject_rules.py` | SessionStart(compact) | Context 壓縮後重注入規則 |
| `path_policy.py` | support module | 載入與驗證 project-local path contract |

---

### P3：Hook 註冊（project settings）

`.claude/settings.json` 註冊 PreToolUse／Stop／UserPromptSubmit／SessionStart hooks。Launcher 使用 quoted `$CLAUDE_PROJECT_DIR`，不依賴 current working directory。

---

### P4：RED verifier

主 agent 委派 `.claude/agents/red-verifier.md`，並提供 requirement、implementation、exact test 與 policy-resolved evidence path。Verifier 在目前 worktree 真實 collect/run，成功後寫 evidence 與 `RED_VERIFIED` phase；不再要求隔離 worktree，也不以 `Agent(*)` 阻擋。

---

### P5：Verification command 依賴

此 reference runtime 固定使用 pytest 與 ruff；path policy 不接受 repository-defined commands。

```bash
python3 -m pip install pytest pytest-cov ruff mutmut
# 整合測試（若需要）
python3 -m pip install pytest-asyncio httpx
# Contract 測試（若需要）
python3 -m pip install pact-python
```

安裝後執行 `python3 -I -m pytest --version` 與 `python3 -I -m ruff --version` 驗證 isolated module runtime。

---

### P6：Smoke Test（驗證 gate 有效）

```bash
# init.sh 會讀取 implementation_roots[0] 並執行同等 smoke test；也可直接：
bash setup/init.sh . .vdd/path-policy.json
```

預期結果：stderr 顯示 `BLOCKED [GATE:SPEC]` 或 `BLOCKED [GATE:RED]`，且 exit code = 2。

---

### P7：MCP Oracle Server（選用）

`.mcp.json`（專案根目錄）：

```json
{
  "mcpServers": {
    "oracle": {
      "type": "stdio",
      "command": "python3",
      "args": [".claude/oracle/server.py"],
      "env": {}
    }
  }
}
```

Oracle MCP server 提供：
- 查詢 configured spec paths 的工具
- Red Evidence 驗證工具
- Traceability matrix 查詢工具

---

## Hook 執行機制詳解

### exit 2 vs JSON output

Hook scripts **必須選擇其中一種**，不可混用：

```python
# 方式 A：exit 2 → 直接阻擋，不需輸出
if violation:
    print("BLOCKED: reason", file=sys.stderr)
    sys.exit(2)

# 方式 B：JSON output → 結構化回應
if violation:
    print(json.dumps({"decision": "block", "reason": "..."}))
    sys.exit(0)  # 注意：exit 0，由 JSON 的 decision 決定
```

Stop hook 必須用方式 B（JSON）。  
PreToolUse 可用方式 A（exit 2）更簡單。

### stop_hook_active 保護

```python
# green_gate.py
data = json.load(sys.stdin)
if data.get("stop_hook_active"):
    sys.exit(0)  # 防止 Stop hook 遞迴呼叫自己
```

### CLAUDE_CODE_STOP_HOOK_BLOCK_CAP

`managed-settings.json` 中設定 `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP: 20`，防止 Stop hook 無限 block（最多 block 20 次，之後允許結束）。

---

## 狀態更新規則

`.vdd/phase` 是此 Claude Code 相容性實作的狀態提示；它不能單獨證明 profile-resolved `GATE:VDD`、`GATE:DEPLOY`、Evidence Envelope 或 Production Verification 已通過。以 target environment 的 Confirm Mode、policy 和可重跑 artifact 為準。

`red-verifier` 負責產生 configured Red Evidence 與 `RED_VERIFIED` phase；Stop hook 只在 verification commands 通過後更新為 `GREEN`。其他 profile／VDD／deploy 狀態由對應外部治理系統管理。

---

*本章對應 Notion 頁面 10 · Claude Code 具體實作*
