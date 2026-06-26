# AGENT_SETUP_PROTOCOL.md — AI Agent 入口文件

> **任何 AI agent 進入使用此框架的專案時，從這裡開始。**

---

## §0 Canonical Glossary（術語速查）

在開始前，確認以下術語的正確含義：

| 術語 | 定義 |
|------|------|
| **STDD** | Specification & Test-Driven Development（≠ TDD，有 Spec 層） |
| **VDD** | Verification & Validation-Driven Development（**≠ Value-Driven，≠ Vulnerability-Driven**）|
| **Canonical Spec** | `specs/` 目錄下的唯一規格來源 |
| **Red Evidence** | `.vdd/red/<req-id>.json`，測試在實作前失敗的機器可驗證紀錄 |
| **Headroom** | Context 壓縮層（**≠ memory engine**） |
| **GATE:ADMIT** | 上游探索閘門（07 的上游，獨立閘門）|

完整術語表：[docs/00-canonical-glossary.md](../docs/00-canonical-glossary.md)

---

## §1 Confirm Mode 清單

進入任何新任務前，執行以下確認清單。**每項都必須通過才能進入 Configure Mode。**

```yaml
confirm_mode_checklist:
  - id: "CM-01"
    check: "CLAUDE.md 已載入，理解所有閘門規則"
    verify: "回答：VDD 代表什麼？GATE:RED 強制等級是什麼？"

  - id: "CM-02"
    check: "managed-settings.json 存在（macOS）"
    command: "ls '/Library/Application Support/ClaudeCode/managed-settings.json'"

  - id: "CM-03"
    check: ".vdd/phase 存在"
    command: "cat .vdd/phase"

  - id: "CM-04"
    check: "6 個 hook scripts 存在"
    command: "ls .claude/hooks/"
    expected: "6 個 .py 檔案"

  - id: "CM-05"
    check: ".claude/settings.json 有 hooks 定義"
    command: "python3 -c \"import json; d=json.load(open('.claude/settings.json')); print(list(d.get('hooks',{}).keys()))\""

  - id: "CM-06"
    check: "red-verifier subagent 存在"
    command: "ls .claude/agents/red-verifier.md"
```

**任何項目 FAIL → 進入 Configure Mode 執行對應 Phase**

---

## §2 Configure Mode（7 Phase 設定序列）

只執行失敗的 Phase，勿重複執行已通過的 Phase。

### P0：地基（macOS 管理員）

```bash
# 確認 managed-settings.json 存在
ls "/Library/Application Support/ClaudeCode/managed-settings.json"

# 若不存在，需管理員執行：
sudo mkdir -p "/Library/Application Support/ClaudeCode"
sudo cp setup/templates/managed-settings.json \
  "/Library/Application Support/ClaudeCode/managed-settings.json"
```

### P1：目錄結構

```bash
mkdir -p specs/{domain,features,contracts/{api,ui},quality,decisions,traceability}
mkdir -p .vdd/red
[ -f .vdd/phase ] || echo "INIT" > .vdd/phase
```

### P2：Hook Scripts

```bash
mkdir -p .claude/hooks
cp <this-repo>/.claude/hooks/*.py .claude/hooks/
# 若在本 repo 內執行，跳過 cp，hooks 已在正確位置
```

### P3：Hook 註冊

```bash
# 確認 settings.json 存在
[ -f .claude/settings.json ] || cp <this-repo>/.claude/settings.json .claude/settings.json
```

### P4：Subagent

```bash
mkdir -p .claude/agents
[ -f .claude/agents/red-verifier.md ] || \
  cp <this-repo>/.claude/agents/red-verifier.md .claude/agents/
```

### P5：Python 依賴

```bash
pip install pytest pytest-cov ruff mutmut
```

### P6：Smoke Test（驗證 gate 有效）

```bash
# 在 .vdd/phase = INIT 時，嘗試 Edit src/ 應被 block
# 正確結果：exit code 2，stderr 顯示 BLOCKED [GATE:SPEC]
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/test.py"}}' | \
  python3 .claude/hooks/pre_impl_gate.py 2>&1; echo "exit: $?"
```

---

## §3 Gate 快速參考

| Gate | 觸發 | 強制等級 | 通過條件 |
|------|------|---------|---------|
| GATE:ADMIT | 新需求 | prompt-only | 需求資訊完整 + Tier 確認 |
| GATE:SPEC | 寫實作前 | **runtime** | `.feature` 存在且非空 |
| GATE:RED | 進入實作前 | **runtime** | `.vdd/phase = RED_VERIFIED` |
| GATE:GREEN | session 結束前 | **runtime（Stop）** | pytest + ruff 全通過 |
| GATE:VDD | merge 前 | config/流程 | 覆蓋率 + 突變測試 + 整合測試 |
| GATE:DEPLOY | 部署後 | 架構外建 | Telemetry 閉環 |

---

## §4 No-Go 條件（永遠阻擋）

以下情況下，**立即停止並回報**，不繼續執行：

1. `.vdd/phase` 不在預期狀態（如 INIT 卻嘗試寫實作）
2. `specs/features/<module>.feature` 不存在，卻被要求實作 `src/<module>.py`
3. Red Evidence（`.vdd/red/<req-id>.json`）不存在，卻要求進入實作
4. 請求弱化測試（pytest.skip / assert True / xfail）
5. T3 需求沒有人工授權就嘗試 auto-dispatch

---

## §5 輸出格式

Agent 完成 Confirm Mode 後，輸出：

```
CONFIRM MODE RESULT:
  CM-01: PASS — VDD = Verification & Validation-Driven Dev, GATE:RED = runtime 強制
  CM-02: PASS — managed-settings.json 存在
  CM-03: PASS — .vdd/phase = RED_VERIFIED
  CM-04: PASS — 6 個 hook scripts 存在
  CM-05: PASS — hooks: PreToolUse, Stop, UserPromptSubmit, PostToolUse, SessionStart
  CM-06: PASS — red-verifier.md 存在

ENVIRONMENT STATUS: READY
NEXT ACTION: 可以開始接受任務
```

若有 FAIL：

```
CONFIRM MODE RESULT:
  CM-02: FAIL — managed-settings.json 不存在

ACTION REQUIRED: 執行 P0（需管理員權限）
  sudo cp setup/templates/managed-settings.json \
    "/Library/Application Support/ClaudeCode/managed-settings.json"
BLOCKED: 環境未就緒，無法開始任務
```

---

## §6 相關文件索引

| 文件 | 用途 |
|------|------|
| [CLAUDE.md](../CLAUDE.md) | Claude Code agent 治理指令（自動載入）|
| [docs/00-canonical-glossary.md](../docs/00-canonical-glossary.md) | 術語唯一定義 |
| [docs/07-canonical-pipeline.md](../docs/07-canonical-pipeline.md) | Pipeline 權威定義 |
| [docs/10-claude-code-implementation.md](../docs/10-claude-code-implementation.md) | 實作細節 |
| [docs/12-ai-agent-readiness-gate.md](../docs/12-ai-agent-readiness-gate.md) | Readiness Gate 完整清單 |
