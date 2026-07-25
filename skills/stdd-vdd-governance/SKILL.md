---
name: stdd-vdd-governance
description: 修改、安裝、驗證或診斷本 repository 的 STDD x VDD governance contract、agent hook、runtime adapter 或 agent configuration 時使用。一般 application change 若不修改 governance pack，不得載入本 skill。
---

# STDD x VDD Governance

本 skill 是 repository 的 progressive disclosure 執行程序。`AGENTS.md` 仍是 runtime-neutral policy entrypoint，`governance/manifest.yaml` 仍是 authority-state entrypoint。

## Start

1. 讀取 `AGENTS.md` 與 `governance/manifest.yaml`。
2. 將任務分類為 `governance_contract`、`claude_runtime`、`codex_adapter`、`agent_configuration` 或 `audit_or_reconciliation`。
3. 只載入 `AGENTS.md` 對應的 bundle。
4. 變更 frozen invariant 或 enforcement surface 前，先說明 authority 與 runtime-evidence boundary。

## Execute

- 優先使用 machine YAML／JSON、schema、hook、adapter 與 deterministic script，避免重複 prose。
- `CLAUDE.md` 與未來其他 runtime-specific instruction 都維持為指向 `AGENTS.md` 的薄 adapter。
- 可重用程序放本 skill；runtime enforcement 放 hook／validator；人類說明放 Notion Human Handbook。
- repository 的 `docs/`、`.plans/`、media 與 assessment snapshot 只作 opt-in reference／audit input。
- 先修改 source artifact，再產生 generated view，並驗證 generation idempotence。
- 保留固定五道 Gate 順序、Stable ID、authority boundary 與既有 safety／test requirements。

## Verify

先選 focused checks：

| Changed surface | Required focused check |
|---|---|
| `governance/**` | `python3 scripts/governance.py validate` 與 `python3 scripts/governance.py render --check` |
| `.claude/**` 或 `setup/**` | `python3 -m unittest tests.test_hooks -v` |
| `integrations/codex/**` 或 Codex mapping | `python3 scripts/codex_adapter.py validate` 與 `python3 -m unittest tests.test_codex_adapter -v` |
| Cross-surface change | focused checks 後執行 `python3 -m unittest discover -s tests -v` |

若目前 branch 含 semantic-reconciliation tooling，任何 Archive／source／digest 變更都要執行其文件宣告的 validation 與 render checks。

## Stop conditions

符合下列任一條件時停止並要求人類指示：

- semantic mismatch 無法 deterministic classification；
- 未經明確授權就需要改變 authority、Gate order、Stable ID meaning、waiver／break-glass approval 或 deployment state；
- 任務要求 runtime enforcement，但缺少 Confirm Mode evidence；
- 完成任務需要弱化 test、policy、security boundary 或 validation threshold。

## Handoff

輸出 `Changed`、`Verified`、`Notes`。在 `Notes` 明確區分 repository configuration、runtime enforcement 與當前 verification evidence。
