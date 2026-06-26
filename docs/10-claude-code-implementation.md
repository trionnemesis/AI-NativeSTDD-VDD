# 10 · Claude Code 具體實作（Implementation）

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
      "Edit(./spec/**)",
      "Edit(./.git/**)",
      "Bash(curl *)",
      "Bash(wget *)",
      "Agent(*)"
    ]
  },
  "disableAutoMode": "disable",
  "disableBypassPermissionsMode": "disable",
  "allowManagedPermissionRulesOnly": true,
  "allowManagedHooksOnly": true,
  "env": {
    "CLAUDE_CODE_STOP_HOOK_BLOCK_CAP": "20"
  }
}
```

**關鍵說明**：
- `defaultMode: "plan"`：所有操作預設需要計畫確認
- `deny: ["Edit(./spec/**)]"`：禁止 agent 修改 spec 檔案
- `allowManagedHooksOnly: true`：hook 只能從此 managed 設定載入
- `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP: 20`：Stop hook 最多 block 20 次，防無限循環

---

### P1：目錄結構初始化

```bash
# 專案規格目錄
mkdir -p specs/{domain,features,contracts/{api,ui},quality,decisions,traceability}

# VDD 狀態目錄
mkdir -p .vdd/red
echo "INIT" > .vdd/phase

# Hook scripts 目錄
mkdir -p .claude/hooks

# Subagent 目錄
mkdir -p .claude/agents
```

---

### P2：Hook Scripts 安裝

將 `.claude/hooks/*.py` 複製到專案的 `.claude/hooks/` 目錄，並設置執行權限：

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
| `test_weakening_guard.py` | PostToolUse Edit/Write | 偵測測試弱化 |
| `inject_spec.py` | UserPromptSubmit | 注入 .vdd/phase 狀態 |
| `reinject_rules.py` | SessionStart(compact) | Context 壓縮後重注入規則 |

---

### P3：Hook 註冊（settings.json）

`.claude/settings.json`：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/inject_spec.py"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/pre_impl_gate.py"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/bash_guard.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/test_weakening_guard.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/green_gate.py"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/hooks/reinject_rules.py"
          }
        ]
      }
    ]
  }
}
```

---

### P4：Subagent 安裝（red-verifier）

```bash
cp <stdd-vdd-repo>/.claude/agents/red-verifier.md .claude/agents/
```

**重要**：subagent 的 `hooks`/`mcpServers`/`permissionMode` 欄位在 plugin agent 的 frontmatter 中是**安全性被忽略**的。Gate hooks 必須在 top-level `settings.json` 中，不能只放在 subagent 定義中。

---

### P5：Python 依賴安裝

```bash
pip install pytest pytest-cov ruff mutmut
# 整合測試（若需要）
pip install pytest-asyncio httpx
# Contract 測試（若需要）
pip install pact-python
```

---

### P6：Smoke Test（驗證 gate 有效）

```bash
# 在 .vdd/phase = INIT 時，嘗試 Edit src/ 應被 block
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/test.py"}}' | \
  python3 .claude/hooks/pre_impl_gate.py 2>&1; echo "exit: $?"
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
- 查詢 specs/ 目錄的工具
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

## 狀態更新範例

```bash
# agent 完成 RED 驗證後手動更新 phase
echo "RED_VERIFIED" > .vdd/phase

# agent 完成 GREEN 後
echo "GREEN" > .vdd/phase

# CI VDD 通過後
echo "VDD_PASS" > .vdd/phase
```

---

*本章對應 Notion 頁面 10 · Claude Code 具體實作*
