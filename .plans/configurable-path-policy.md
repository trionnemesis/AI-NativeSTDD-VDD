# 可設定的 STDD×VDD Path Policy

## Overview

將 runtime hooks 與安裝流程對 `src/`、`specs/`、`tests/` 的固定假設收斂成單一 `.vdd/path-policy.json`。設定檔是 opt-in override；不存在時使用目前相容預設。設定格式錯誤時 gate 必須 loud fail，不可退回猜測或靜默放行。此變更只調整 implementation/reference layer，不改變 `governance/manifest.yaml` 的 `SHADOW_NON_AUTHORITATIVE` authority state。

## Design Principles

1. **Single policy home**：所有 repository path/layout override 只從 `.vdd/path-policy.json` 載入；不接受 executable/shell command。
2. **Backward compatible**：未提供設定時，`src/`、`spec(s)/features/`、`.vdd/red/`、`tests/`、pytest 與 ruff 行為維持原樣。
3. **Deterministic and fail closed**：不自動猜測 framework layout；未知欄位或無效路徑直接阻擋 gate。
4. **Minimum enforcement**：machine-wide settings 不綁定 target folder；path-aware hooks 由 project settings 註冊。

## Architecture

```text
.vdd/path-policy.json
          |
          v
  hooks/path_policy.py
    |     |      |      |
    v     v      v      v
  SPEC   RED   GREEN   guards
          |
          v
 setup + readiness docs
```

各 hook 共用同一個 loader 與 path matcher；bootstrap 安裝相容預設，文件與 smoke test 從設定取得 target path。

### Option A: Explicit path policy

- target 明確宣告 implementation roots、spec templates、protected spec roots、test patterns 與 test roots。
- 行為 deterministic，可在 temp repository E2E 驗證。
- 未設定時可保持目前相容行為。

### Option B: Auto-detect project layout

- 依 `package.json`、`pyproject.toml`、framework marker 或現存目錄猜測 layout。
- 同一 monorepo 可能同時命中多個規則，gate 邊界會隨檔案增減漂移。
- 難以證明 rollback 與 protected path coverage。

**Recommendation: Option A** — 可用同一組明確設定重跑 hook tests，且不需要新增語言／framework detector。

## Configuration

```json
{
  "implementation_roots": ["src"],
  "feature_spec_templates": [
    "specs/features/{module}.feature",
    "spec/features/{module}.feature"
  ],
  "protected_spec_roots": ["spec", "specs"],
  "red_evidence_template": ".vdd/red/{module}.json",
  "test_file_patterns": ["*test*", "*spec*"],
  "test_roots": ["tests"],
  "spec_change_paths": ["spec", "specs"]
}
```

Path placeholders：`{module}` 是檔名 stem、`{relative}` 是相對於命中的 implementation root 且移除 suffix 的路徑、`{path}` 是 repository-relative 且移除 suffix 的完整路徑。Policy 只描述 path/layout，不允許自訂 shell command。

Precedence：

1. Target repository 的 `.vdd/path-policy.json`。
2. Hook 內建 compatibility defaults（設定檔不存在時）。

## Implementation Plan

### Phase 1: Runtime policy contract

**File: `.claude/hooks/path_policy.py`**

#### 1a. 新增 stdlib-only loader、schema checks 與 real-path matcher (~330 lines)

提供 `load_policy()`、`implementation_context()`、`render_path_template()`、`matches_test_path()` 與 path validation；拒絕 absolute root、`..`、未知欄位與 symlink crossing。

**Files: `.claude/hooks/pre_impl_gate.py`, `.claude/hooks/bash_guard.py`, `.claude/hooks/green_gate.py`, `.claude/hooks/inject_spec.py`, `.claude/hooks/reinject_rules.py`, `.claude/hooks/test_weakening_guard.py`**

#### 1b. 將固定 path 改由 policy 解析 (~200 net lines)

SPEC/RED 依命中的 implementation root 產生 module context；Bash guard 依 roots 產生 escaped patterns；GREEN 對 `test_roots` 執行固定 pytest/ruff。無設定時使用現行 defaults。

**File: `tests/test_hooks.py`**

#### 1c. 新增 default compatibility、custom layout、invalid policy 與 hook integration tests (~400 lines)

**Tests for Phase 1:**

- 無設定時 `src/test.py` 仍受既有 SPEC/RED gate 保護。
- custom `app/` + `requirements/features/` + custom evidence template 可通過完整 pre-implementation chain。
- custom policy 下未列入的 `src/` 不會被誤擋，`app/` Bash write 會被擋。
- invalid policy loud fail；repository 外 absolute path 不會誤判為 target implementation。
- custom `test_roots` 會被 GREEN 使用，且只從 `RED_VERIFIED` 升為 `GREEN`。
- custom test pattern 仍會阻擋已知 weakening pattern。
- policy/implementation/spec symlink escape 與 invalid policy 均 fail closed。
- GREEN custom root、PreToolUse weakening prevention 與 policy rollback transition 可重跑。

### Phase 2: Bootstrap and reference alignment

**File: `setup/templates/path-policy.json`**

#### 2a. 新增 compatibility default template (~40 lines)

**File: `setup/init.sh`**

#### 2b. 支援 optional policy source、原子驗證替換並避免 custom layout 時建立固定 spec tree (~90 net lines)

若 target 已有 policy 或第二參數提供 policy，保留 custom layout；否則安裝 default template 並保留舊目錄初始化。

**Files: `CLAUDE.md`, `setup/AGENT_SETUP_PROTOCOL.md`, `docs/01-method-architecture.md`, `docs/02-canonical-spec.md`, `docs/03-change-management.md`, `docs/06-anti-fake-test.md`, `docs/09-agent-cli-evaluation.md`, `docs/10-claude-code-implementation.md`, `docs/11-headroom-context.md`, `docs/12-ai-agent-readiness-gate.md`, `.claude/settings.json`, `setup/templates/managed-settings.json`**

#### 2c. 把 normative 固定資料夾敘述改成 policy contract，保留 default examples (~200 changed lines)

移除 managed settings 的 fixed spec deny 與 `Agent(*)`，不啟用 `allowManagedHooksOnly`；project protected-spec hook 讀取 target path policy，`.git/` 與 curl/wget 底線不變。

**Tests for Phase 2:**

- default init 在 temp target 產生相容目錄與 `.vdd/path-policy.json`。
- custom init 不額外建立 `specs/`，且 smoke test 使用 custom implementation root。
- 文件中的 normative gate 敘述與設定 key 一致。

### Phase 3: Focused verification and rollback evidence

**Files: working tree**

#### 3a. 執行 related suite、static syntax 與 governance bundle (~0 product lines)

在 virtualenv 執行 hook tests、完整 unittest、governance validate、render check、py_compile 與 `git diff --check`。不再新增 adversarial review loop。

**Tests for Phase 3:**

- 所有 Phase 1/2 tests 綠。
- validator 與 deterministic render 綠。
- rollback dry-run 證明刪除 target policy 即回復 compatibility defaults，無 data migration。

## Integration Issues & Edge Cases

1. **Absolute tool path**：先 realpath 再轉 repository-relative；repository 外路徑不套用 target policy。
2. **Nested modules with duplicate stems**：custom policy 可用 `{relative}` 或 `{path}` 避免同名 spec/evidence collision；default 保留舊 `{module}` 行為。
3. **Malformed local policy**：任何 hook 都 loud fail，避免 typo 讓 protected paths 失效。
4. **Policy update**：`.vdd/path-policy.json` 是 Configure Mode 輸入，invalid schema 會使 hooks fail closed。
5. **Bash syntax coverage**：延續既有 deterministic bypass patterns，configured roots 會 regex escape；不宣稱完整 shell sandbox。
6. **Test layout**：`test_roots` 可設定；GREEN 使用固定 `-I -m pytest/ruff`，policy 不能注入 command。
7. **Authority boundary**：不修改 manifest authority、canonical pipeline 或 cutover preconditions。

## Files Changed Summary

| File | Phase | Changes |
|---|---:|---|
| `.claude/hooks/path_policy.py` | 1 | NEW — shared policy loader and matchers |
| `.plans/configurable-path-policy.md` | 1-3 | NEW — design, rollout, rollback, verification plan |
| `.claude/hooks/{pre_impl_gate,bash_guard,green_gate,inject_spec,reinject_rules,test_weakening_guard}.py` | 1 | consume/reinject configured paths and protect runtime state |
| `tests/test_hooks.py` | 1-2 | runtime and init regression tests |
| `setup/templates/path-policy.json` | 2 | NEW — compatibility defaults |
| `setup/init.sh` | 2 | default/custom policy bootstrap |
| `CLAUDE.md` | 2 | policy-aware agent contract summary |
| `setup/AGENT_SETUP_PROTOCOL.md` | 2 | policy-aware Confirm/Configure Mode |
| `docs/01-method-architecture.md` | 2 | configured implementation boundary |
| `docs/02-canonical-spec.md` | 2 | configured spec boundary |
| `docs/03-change-management.md` | 2 | configured protected-spec boundary |
| `docs/06-anti-fake-test.md` | 2 | policy-resolved evidence and runner wording |
| `docs/09-agent-cli-evaluation.md` | 2 | machine-wide versus project hook trust boundary |
| `docs/10-claude-code-implementation.md` | 2 | installation reference |
| `docs/11-headroom-context.md` | 2 | policy-aware context reinjection reference |
| `docs/12-ai-agent-readiness-gate.md` | 2 | readiness and smoke test reference |
| `.claude/agents/red-verifier.md` | 2 | policy-aware paths; remove worktree isolation |
| `.claude/settings.json` | 2 | root-aware fallback launchers and PreToolUse weakening guard |
| `setup/templates/managed-settings.json` | 2 | remove fixed-folder, Agent, and managed-only hook restrictions |
| `requirements-governance.txt`, `.github/workflows/governance-shadow.yml` | 3 | hook E2E dependencies and CI path coverage |

**Total new implementation/config code**: ~500 lines / **Net new test code**: ~210 lines

## Rollout Plan

1. Merge Phase 1 with policy absent by default in existing targets; validate compatibility defaults and custom temp target.
2. Merge Phase 2 template/bootstrap/docs；new targets receive default policy，custom targets may provide policy before init or as init argument 2.
3. Run focused verification；rollout remains non-authoritative. Rollback 是 `git revert` 後移除 target `.vdd/path-policy.json`；無 schema/data migration 或 authority cutover。

Each phase is independently mergeable and testable.
