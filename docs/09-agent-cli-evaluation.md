# 09 · AI Agent CLI 評估（Agent CLI Evaluation）

---

## 概述

本章記錄選擇 Claude Code 作為 STDD×VDD 執行平台的決策依據，以 28 個評估標準進行比較分析。

---

## 評估結論

**Claude Code 是 STDD×VDD 治理層的最佳執行平台。**

核心理由：
1. PreToolUse hook 在 `bypassPermissions` 前觸發（唯一真實 runtime gate）
2. Stop hook 可強制阻擋 session 結束（GREEN gate 強制）
3. `managed-settings.json` 提供不可覆蓋的 org-level 設定
4. Subagent（Plugin agents）支援工作流拆分與隔離

---

## 28 標準評估矩陣

### 類別 A：Hook 機制（最關鍵）

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| A1 | PreToolUse hook | ✅ 完整 | ❌ 無 | ❌ 無 |
| A2 | Stop hook（阻擋結束）| ✅ 支援 | ❌ 無 | ❌ 無 |
| A3 | Hook bypass 保護 | ✅ managed-settings | ❌ 無 | ❌ 無 |
| A4 | PostToolUse hook | ✅ 支援 | ❌ 無 | ❌ 無 |
| A5 | UserPromptSubmit hook | ✅ 支援 | ❌ 無 | ❌ 無 |
| A6 | SessionStart hook | ✅ 支援 | ❌ 無 | ❌ 無 |

### 類別 B：Org-Level 設定

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| B1 | managed-settings.json | ✅ precedence 1 | ❌ 無 | ❌ 無 |
| B2 | disableBypassPermissionsMode | ✅ 支援 | ❌ 無 | ❌ 無 |
| B3 | allowManagedHooksOnly | ✅ 支援 | ❌ 無 | ❌ 無 |
| B4 | defaultMode: plan | ✅ 設定 | ⚠️ 部分 | ❌ 無 |

### 類別 C：Subagent / 工作流

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| C1 | Plugin agents（.claude/agents/）| ✅ 完整 | ❌ 無 | ❌ 無 |
| C2 | Worktree isolation | ✅ 支援 | ❌ 無 | ❌ 無 |
| C3 | 子 agent disallowedTools | ✅ 支援 | ❌ 無 | ❌ 無 |
| C4 | 並行 agent 執行 | ✅ Agent SDK | ❌ 無 | ❌ 無 |
| C5 | MCP server 整合 | ✅ 完整 | ⚠️ 有限 | ❌ 無 |

### 類別 D：規格與 Spec 整合

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| D1 | CLAUDE.md 自動載入 | ✅ 支援 | ⚠️ .cursorrules | ⚠️ .github/copilot-instructions |
| D2 | 路徑 scoped rules | ✅ 支援 | ❌ 無 | ❌ 無 |
| D3 | 設定檔優先權層次 | ✅ 3 層 | ⚠️ 1 層 | ⚠️ 1 層 |
| D4 | Git worktree 整合 | ✅ 原生 | ❌ 無 | ❌ 無 |

### 類別 E：Context 管理

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| E1 | Context compaction | ✅ 自動 | ⚠️ 有限 | ❌ 無 |
| E2 | SessionStart(compact) hook | ✅ 支援 | ❌ 無 | ❌ 無 |
| E3 | Headroom 機制 | ✅ 設計支援 | ❌ 無 | ❌ 無 |
| E4 | 跨 session 記憶 | ✅ memory/ | ⚠️ 有限 | ❌ 無 |

### 類別 F：安全與審計

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| F1 | Tool 使用紀錄 | ✅ 完整 | ⚠️ 部分 | ⚠️ 部分 |
| F2 | Deny 規則 | ✅ managed 層 | ❌ 無 | ❌ 無 |
| F3 | 網路存取控制 | ✅ Bash(curl*) deny | ⚠️ 有限 | ❌ 無 |
| F4 | Plan mode 預設 | ✅ 可設定 | ❌ 無 | ❌ 無 |

### 類別 G：生態系統

| # | 標準 | Claude Code | Cursor | GitHub Copilot |
|---|------|------------|--------|----------------|
| G1 | CLI 可腳本化 | ✅ 完整 | ⚠️ 有限 | ❌ 無 |
| G2 | 開源 hook 範例 | ✅ 豐富 | ❌ 無 | ❌ 無 |
| G3 | Agent SDK | ✅ 完整 | ❌ 無 | ❌ 無 |
| G4 | Model 可替換 | ✅ 可配置 | ✅ 支援 | ❌ 固定 |

---

## 關鍵技術分析

### PreToolUse Hook 的重要性

**PreToolUse 是唯一在 `bypassPermissions` 模式前觸發的 hook。**

```
使用者請求
    ↓
PreToolUse Hook  ← STDD:SPEC + RED gates 在此執行
    ↓
Permission 檢查（bypassPermissions 影響此層）
    ↓
Tool 執行
    ↓
PostToolUse Hook
```

即使 agent 以 `bypassPermissions` 模式執行，PreToolUse exit 2 仍會阻擋工具調用。  
這是 STDD×VDD 治理層能 runtime 強制的根本原因。

### managed-settings.json 的 Precedence 1

設定優先權（高到低）：
1. `managed-settings.json`（org-level，本檔）
2. `.claude/settings.json`（project-level）
3. `~/.claude/settings.json`（user-level）
4. CLI flags

**`allowManagedHooksOnly: true` 確保 hook 只從 managed 設定載入**，防止 agent 自行修改 hooks。

---

## 為什麼不選擇其他平台

| 平台 | 拒絕理由 |
|------|---------|
| Cursor | 無 runtime hook，只有 prompt-level 規則，AI 可忽略 |
| GitHub Copilot | 無 CLI 自動化，無 hook，純建議模式 |
| Devin | 封閉 API，無法整合自訂 hook |
| 自建 LangGraph | 開發成本高，需自建整個 tool call 基礎設施 |

---

*本章對應 Notion 頁面 09 · Agent CLI 評估*
