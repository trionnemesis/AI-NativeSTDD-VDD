# AI Agent Repository Contract

## 範圍與受眾

本 repository 是提供 AI coding agent 使用的 machine governance 與 runtime configuration pack。預設使用者是 agent、hook runtime、validator 與 adapter maintainer。

人類教學內容屬於 Notion Human Handbook。repository 內的 `docs/`、media、assessment snapshot 與 `.plans/` 是過渡期 reference／audit surface，預設 coding context **不得**載入。

本檔規則適用於整個 repository。

## Authority boundary

1. 解讀任何 contract 前，先讀 `governance/manifest.yaml`。
2. 以 manifest 的當前 authority state 為準；不得從檔案存在、hook、通過的測試、merged PR 或 generated view 推定 authority cutover。
3. repository 為 `SHADOW_NON_AUTHORITATIVE` 期間，與 Notion 的 semantic mismatch 必須 loud fail，並交由人類裁決。
4. `generated/` 是衍生 evidence。修改其宣告的 source 後重新產生；不得直接編輯 generated output。

## 最小載入協定

只載入本檔、`governance/manifest.yaml` 與一個 primary task bundle。需要第二個 bundle 時，只補第一個 bundle 缺少的檔案。不得因 cross-link 遞迴讀取所有內容。

| Task bundle | 載入範圍 |
|---|---|
| `governance_contract` | 相關 `governance/registries/`、一個或多個 `governance/gates/`、適用的 `governance/profiles/`，以及必要的 schema／example |
| `claude_runtime` | `.claude/settings.json`、受影響的 `.claude/hooks/` 或 `.claude/agents/` 檔案、`setup/AGENT_SETUP_PROTOCOL.md`、`tests/test_hooks.py` |
| `codex_adapter` | `integrations/codex/adapter.yaml`、`scripts/codex_adapter.py`、`tests/test_codex_adapter.py`；只有需要設計理由時才讀 `docs/25-codex-adapter.md` |
| `agent_configuration` | `governance/gates/regression.yaml`、變更的 runtime／config surface 與其 focused tests |
| `audit_or_reconciliation` | 只有任務明確要求歷史、比較或 audit 時，才載入歷史 `docs/`、`.plans/`、assessment snapshot 或 generated report |

需要可重用的執行程序時，按需載入 `skills/stdd-vdd-governance/SKILL.md`。不得把完整 Gate、glossary 或 profile 定義複製到 prompt 檔案。

## Frozen invariants

- Canonical pipeline：`GATE:SPEC → GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY`。
- `GATE:ADMIT` 位於上游；`GATE:REGRESSION` 是 auxiliary gate。兩者都不是第六道 pipeline Gate。
- Stable ID 不得被靜默重用或重新定義。
- 不得為了通過檢查而弱化 test、validation、security、authorization、policy 或 evidence requirements。
- Contract 存在只代表 `contract_defined`，不代表 `runtime_enforced` 或 `verified`。
- Authority cutover、waiver approval、break-glass approval、deployment 與 merge 都是明確的人類決策，除非當前 contract 另有規定。

## 變更流程

1. 分類任務並選擇最小 bundle。
2. 編輯前確認 manifest authority state 與適用的 gate／profile。
3. 保留無關的 worktree 變更，只做最小正確修改。
4. 先執行 focused validation，再執行 related suite；只有存在相關命令時才執行 lint／build。
5. 只報告實際執行的命令，並區分 `contract_defined`、`configured`、`runtime_enforced` 與 `verified`。

## 驗證命令

依變更 surface 執行相關命令：

```bash
python3 scripts/governance.py validate
python3 scripts/governance.py render --check
python3 scripts/codex_adapter.py validate
python3 -m unittest discover -s tests -v
```

若目前 branch 含有 Phase 2 semantic-reconciliation tooling，Archive／source／digest 變更還要執行該工具文件宣告的 validator 與 render check。缺少只存在其他 branch 的工具不等於通過，必須標示為 unavailable。

## Agent-facing surfaces

- `AGENTS.md`：runtime-neutral routing 與 repository policy。
- `CLAUDE.md`：薄層 Claude Code adapter；不得重複本檔 contract。
- `skills/`：progressive disclosure 的執行程序。
- `.claude/`：Claude Code hooks、settings 與 subagent configuration。
- `integrations/`：其他 runtime adapters。
- `governance/`：machine-readable contracts 與 schemas。
- `setup/`：target project 安裝與 Confirm／Configure protocol。
- `tests/`、`scripts/`：deterministic validation 與 evidence collection。

## Handoff format

```text
Changed:
- ...

Verified:
- ...

Notes:
- authority/runtime/evidence limits or remaining work
```
