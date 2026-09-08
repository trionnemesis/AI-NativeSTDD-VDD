# AGENT_SETUP_PROTOCOL.md — AI Agent 入口文件

> **任何 AI agent 進入使用此框架的專案時，從這裡開始。**

> **Authority preflight（MCR:2026:004）**：先讀 `governance/manifest.yaml`。若 `repository_state` 為 `SHADOW_NON_AUTHORITATIVE`，不得把 repo shadow 宣稱為 canonical，也不得執行 authority cutover。

---

## §0 Canonical Glossary（術語速查）

在開始前，確認以下術語的正確含義：

| 術語 | 定義 |
|------|------|
| **STDD** | Specification & Test-Driven Development（≠ TDD，有 Spec 層） |
| **VDD** | Verification & Validation-Driven Development（**≠ Value-Driven，≠ Vulnerability-Driven**）|
| **Canonical Spec** | `.vdd/path-policy.json` 的 `protected_spec_roots` 所宣告之唯一規格來源；相容預設為 `spec/`、`specs/` |
| **Red Evidence** | `red_evidence_template` 所宣告的機器可驗證 JSON；相容預設為 `.vdd/red/<module>.json` |
| **Headroom** | Context 壓縮層（**≠ memory engine**） |
| **GATE:ADMIT** | 上游探索閘門（07 的上游，獨立閘門）|

完整 machine-readable shadow：[`governance/glossary.yaml`](../governance/glossary.yaml)
Human reference：[docs/00-canonical-glossary.md](../docs/00-canonical-glossary.md)

---

## §1 Confirm Mode 清單

進入任何新任務前，執行以下確認清單。**每項都必須通過才能進入 Configure Mode。**

```yaml
confirm_mode_checklist:
  - id: "CM-00"
    check: "authority manifest 與 task-relevant governance contracts 存在"
    command: "test -f governance/manifest.yaml && test -d governance/gates && test -d governance/profiles"

  - id: "CM-01"
    check: "CLAUDE.md 已載入，理解所有閘門規則"
    verify: "回答：VDD 代表什麼？GATE:RED 強制等級是什麼？"

  - id: "CM-02"
    check: "managed settings 保留 permission 底線且未禁用 project hooks（macOS）"
    command: "python3 -c \"import json; d=json.load(open('/Library/Application Support/ClaudeCode/managed-settings.json')); assert d.get('allowManagedPermissionRulesOnly') is True and 'allowManagedHooksOnly' not in d\""

  - id: "CM-03"
    check: ".vdd/path-policy.json 有效且 .vdd/phase 存在"
    command: "python3 .claude/hooks/path_policy.py && cat .vdd/phase"

  - id: "CM-04"
    check: "7 個 hook entrypoints 與 path_policy.py 存在"
    command: "ls .claude/hooks/"
    expected: "8 個 .py 檔案"

  - id: "CM-05"
    check: "project settings 有 PreToolUse／Stop／UserPromptSubmit hooks"
    command: "python3 -c \"import json; h=json.load(open('.claude/settings.json'))['hooks']; assert all(e in h for e in ['PreToolUse','Stop','UserPromptSubmit'])\""

  - id: "CM-06"
    check: "red-verifier subagent 存在"
    command: "test -f .claude/agents/red-verifier.md"

  - id: "CM-07"
    check: "System／Change Profile、Evidence 與 Release contract 可載入"
    command: "test -f governance/profiles/system.yaml && test -f governance/profiles/change.yaml && test -f governance/gates/vdd.yaml && test -f governance/gates/deploy.yaml"

  - id: "CM-08"
    check: "read-side isolation guard 已註冊於 PreToolUse Read|Grep|Glob"
    command: "python3 -c \"import json; p=json.load(open('.claude/settings.json'))['hooks']['PreToolUse']; assert any(e.get('matcher')=='Read|Grep|Glob' and any('read_isolation_guard.py' in h['command'] for h in e['hooks']) for e in p)\""
    note: "檔案存在只證明 configured；還需 CM-03 的 .vdd/phase 才能決定 lane"
```

`GATE:RED` 的 `agent_isolation_enforced` 有兩側，兩側都由 `.vdd/phase` 決定方向：

| phase | lane | 不可讀 |
|---|---|---|
| `RED_VERIFIED`、`GREEN` | implementation | configured `test_roots` 與符合 `test_file_patterns` 的檔案 |
| 其他（含 `INIT` 與檔案不存在） | test_authoring | configured `implementation_roots` |

`protected_spec_roots` 兩側都可讀——Canonical Spec 是雙方共同的約束來源。

**任何項目 FAIL → 進入 Configure Mode 執行對應 Phase**

---

## §2 Configure Mode（7 Phase 設定序列）

只執行失敗的 Phase，勿重複執行已通過的 Phase。

### P0：地基（macOS 管理員）

```bash
# 確認 managed-settings.json 存在
ls "/Library/Application Support/ClaudeCode/managed-settings.json"

# 若不存在，需由管理員安裝：
sudo mkdir -p "/Library/Application Support/ClaudeCode"
sudo cp setup/templates/managed-settings.json \
  "/Library/Application Support/ClaudeCode/managed-settings.json"
```

### P1：Path policy 與治理目錄

```bash
# Compatibility layout
bash setup/init.sh <target-project-dir>

# Custom layout
bash setup/init.sh <target-project-dir> <path-policy-json>
```

Path policy 是 project-local deterministic **path/layout** contract。Custom policy 可只覆寫需要改動的 key，其餘使用 compatibility defaults；test directories 使用 `test_roots`。Policy 不接受 executable/shell command，也不得靠 framework heuristic 猜測。

若是從本 template 手動套用，還必須複製 agent 指令所引用的 authority artifacts：

```bash
cp -R <this-repo>/governance ./governance
mkdir -p generated scripts
cp <this-repo>/generated/notion-canonical-view.md generated/
cp <this-repo>/scripts/governance.py scripts/
cp <this-repo>/requirements-governance.txt .
```

### P2：Hook Scripts

```bash
mkdir -p .claude/hooks
cp <this-repo>/.claude/hooks/*.py .claude/hooks/
# 若在本 repo 內執行，跳過 cp，hooks 已在正確位置
```

### P3：Project Hook 註冊

```bash
# project settings 註冊 path-aware hooks
python3 -c "import json; h=json.load(open('.claude/settings.json'))['hooks']; assert all(e in h for e in ['PreToolUse','Stop','UserPromptSubmit'])"
```

### P4：RED verifier

```bash
test -f .claude/agents/red-verifier.md
```

### P5：Verification command 依賴

```bash
# fixed managed RED/GREEN toolchain
python3 -m pip install pytest pytest-cov ruff mutmut
```

執行 `python3 -I -m pytest --version` 與 `python3 -I -m ruff --version` 取得可重跑 readiness 結果。

### P6：Smoke Test（驗證 gate 有效）

```bash
# init.sh 讀取 implementation_roots[0] 並對 <root>/test.py 執行 smoke test
bash setup/init.sh . .vdd/path-policy.json
# 正確結果：P6 PASS；hook exit code 2 且 stderr 顯示 BLOCKED [GATE:SPEC]
```

---

## §3 Gate 快速參考

| Gate | 觸發 | 強制等級 | 通過條件 |
|------|------|---------|---------|
| GATE:ADMIT | Signal 形成 Change Intent 前 | deterministic policy + target hooks | source/trust/provenance/dedup/tier/queue/DoR 都通過；不是第六道 Gate |
| GATE:SPEC | 寫實作前 | profile policy + target runtime hook | Delta/Impact/Stable ID/profile/applicable contracts/evidence plan 完整 |
| GATE:RED | Independent test 後 | target runtime hook + profile policy | FEATURE/DEFECT baseline-red，或其他 profile 的 accepted alternative evidence |
| GATE:GREEN | 實作後 | target Stop hook + profile policy | required tests、static analysis、lint/type/build、protected-test integrity；TIA 不得弱化 full regression |
| GATE:VDD | merge/release 前 | profile-resolved quality contract | applicable quality evidence 和有效 waiver 完整 |
| GATE:DEPLOY | 受控發布前 | release policy / external platform | Release Profile、rollout、observation、rollback、provenance/runbook 就緒 |

---

## §4 No-Go 條件（永遠阻擋）

以下情況下，**立即停止並回報**，不繼續執行：

1. `.vdd/phase` 不在預期狀態（如 INIT 卻嘗試寫實作）
2. `feature_spec_templates` 解析後的 spec 不存在，卻被要求修改 configured implementation root
3. `red_evidence_template` 解析後的 JSON 不存在，卻要求進入實作
4. 請求弱化測試（pytest.skip / assert True / xfail）
5. T3 需求沒有人工授權就嘗試 auto-dispatch
6. 為了讀取當前 lane 不可讀的一側，而改用 Bash、改寫 `.vdd/phase` 或停用 hook

---

## §5 輸出格式

Agent 完成 Confirm Mode 後，輸出：

```
CONFIRM MODE RESULT:
  CM-00: PASS — governance manifest/gates/profiles 存在，authority state 已讀取
  CM-01: PASS — VDD = Verification & Validation-Driven Dev, GATE:RED = runtime 強制
  CM-02: PASS — managed-settings.json 存在
  CM-03: PASS — path policy JSON valid；.vdd/phase = RED_VERIFIED
  CM-04: PASS — 7 個 hook entrypoints + path_policy.py 存在
  CM-05: PASS — project hooks: PreToolUse, Stop, UserPromptSubmit, SessionStart
  CM-06: PASS — red-verifier subagent 存在
  CM-07: PASS — profile、VDD 與 deploy contracts 可載入
  CM-08: PASS — read_isolation_guard.py 已註冊於 Read|Grep|Glob

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
| [docs/24-system-change-profiles.md](../docs/24-system-change-profiles.md) | assertion applicability 與 risk tailoring |
| [docs/21-evidence-provenance-audit-contract.md](../docs/21-evidence-provenance-audit-contract.md) | Evidence Envelope 與 audit boundary |
