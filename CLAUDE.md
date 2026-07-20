# Claude Code Adapter

本檔是薄層 Claude Code entrypoint。repository-wide policy 位於 `AGENTS.md`；machine authority state 與 frozen invariants 位於 `governance/manifest.yaml`。

## First action

1. 讀取 `AGENTS.md`。
2. 讀取 `governance/manifest.yaml`。
3. 從 `AGENTS.md` 選擇一個 task bundle，只載入該 bundle 的檔案。
4. 若任務需要宣稱 target project readiness 或 enforcement，讀取 `setup/AGENT_SETUP_PROTOCOL.md` 並執行 Confirm Mode。

預設不得載入完整 `docs/` tree、Notion workspace、assessment archive、media 或 MCR history。

## Claude Code runtime surfaces

- Hook registration：`.claude/settings.json`
- Enforcement scripts：`.claude/hooks/`
- Independent RED verifier：`.claude/agents/red-verifier.md`
- Target path policy：`.vdd/path-policy.json`；相容行為由 hook implementation 與 setup template 定義
- Install／readiness protocol：`setup/AGENT_SETUP_PROTOCOL.md`
- Hook regression tests：`tests/test_hooks.py`

Hook 檔案存在只證明 `configured`。只有 registration、execution point、target path policy 與可重跑 evidence 全部通過 Confirm Mode，才能宣稱 `runtime_enforced`。

## Claude-specific rules

- Hook exit code 與 deterministic validator failure 是 blocking evidence，不得重新解讀為 prompt suggestion。
- 不得用 Bash redirection 或替代工具繞過 `PreToolUse` guard。
- 不得弱化、跳過、刪除或自行核准 protected test、policy、evidence、waiver 或 release requirement。
- Context compaction 後遵循 `SessionStart(compact)` reinjection hook；若 hook 未執行，繼續前重新載入 `AGENTS.md` 與 manifest。
- 本 adapter 必須保持精簡。新 methodology prose 放 Notion；可重用 agent procedure 放 `skills/`；machine rule 放 `governance/`；enforcement 放 hook 或 validator。

## 驗證

Claude runtime 變更至少執行：

```bash
python3 -m unittest tests.test_hooks -v
python3 scripts/governance.py validate
```

變更跨越 governance、setup、adapter 或 generated-output boundary 時，再執行 repository-wide suite。
