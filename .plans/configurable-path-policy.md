# 可設定的 STDD×VDD Path Policy

## Overview

將 runtime hooks 與安裝流程對 `src/`、`specs/`、`tests/` 的固定假設收斂成單一 `.vdd/path-policy.json`。設定檔是 opt-in override；不存在時使用目前相容預設，既有 target 行為完全不變。設定格式錯誤時 gate 必須 loud fail，不可退回猜測或靜默放行。此變更只調整 implementation/reference layer，不改變 `governance/manifest.yaml` 的 `SHADOW_NON_AUTHORITATIVE` authority state。

## Design Principles

1. **Single policy home**：所有 path 與 GREEN command override 只從 `.vdd/path-policy.json` 載入。
2. **Backward compatible**：未提供設定時，`src/`、`spec(s)/features/`、`.vdd/red/`、`tests/`、pytest 與 ruff 行為維持原樣。
3. **Deterministic and fail closed**：不自動猜測 framework layout；未知欄位、無效路徑或命令格式直接阻擋 gate。
4. **No shell expansion**：GREEN commands 以 argv array 執行，不透過 shell；path 比對先解析為 repository-relative real path。

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

- target 明確宣告 implementation roots、spec templates、protected spec roots、test patterns 與 GREEN commands。
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
  "spec_change_paths": ["spec", "specs"],
  "command_allowlist": ["{python}", "ruff"],
  "red_collect_command": ["{python}", "-m", "pytest", "--collect-only", "{test_path}", "-k", "{test_name}"],
  "red_run_command": ["{python}", "-m", "pytest", "{test_path}", "-k", "{test_name}", "-v"],
  "green_commands": [
    ["{python}", "-m", "pytest", "tests/", "-q", "-m", "not integration"],
    ["ruff", "check", "."]
  ]
}
```

Path placeholders：`{module}` 是檔名 stem、`{relative}` 是相對於命中的 implementation root 且移除 suffix 的路徑、`{path}` 是 repository-relative 且移除 suffix 的完整路徑。RED argv 另支援 `{test_path}`、`{test_name}`、`{requirement_id}`；GREEN argv 只支援 `{python}`。所有 executable 都必須列在 `command_allowlist`，shell trampolines 禁止。

Precedence：

1. Target repository 的 `.vdd/path-policy.json`。
2. Hook 內建 compatibility defaults（設定檔不存在時）。

## Implementation Plan

### Phase 1: Runtime policy contract

**File: `.claude/hooks/path_policy.py`**

#### 1a. 新增 stdlib-only loader、schema checks 與 real-path matcher (~390 lines)

提供 `load_policy()`、`implementation_context()`、`render_path_template()`、`matches_test_path()` 與 `expand_command()`；拒絕 absolute root、`..`、未知欄位與非 argv command。

**Files: `.claude/hooks/pre_impl_gate.py`, `.claude/hooks/bash_guard.py`, `.claude/hooks/green_gate.py`, `.claude/hooks/inject_spec.py`, `.claude/hooks/reinject_rules.py`, `.claude/hooks/test_weakening_guard.py`**

#### 1b. 將固定 path／command 改由 policy 解析 (~160 net lines)

SPEC/RED 依命中的 implementation root 產生 module context；Bash guard 依 roots 產生 escaped patterns；GREEN 逐一執行 argv commands；spec diff 與 test weakening 依設定判定。無設定時使用現行 defaults。

**File: `tests/test_hooks.py`**

#### 1c. 新增 default compatibility、custom layout、invalid policy 與 command E2E tests (~700 lines)

**Tests for Phase 1:**

- 無設定時 `src/test.py` 仍受既有 SPEC/RED gate 保護。
- custom `app/` + `requirements/features/` + custom evidence template 可通過完整 pre-implementation chain。
- custom policy 下未列入的 `src/` 不會被誤擋，`app/` Bash write 會被擋。
- invalid policy loud fail；repository 外 absolute path 不會誤判為 target implementation。
- custom GREEN argv commands 不依賴 `tests/` 或 ruff 且只從 `RED_VERIFIED` 升為 `GREEN`。
- custom test pattern 仍會阻擋已知 weakening pattern。
- managed permissions 保護 project-scoped hook／policy control plane；policy/implementation/spec symlink escape、absolute/dynamic Bash path 與 non-UTF8 policy 均 fail closed。
- custom RED collect/run wrapper、GREEN order/failure/secret-redaction 與 policy rollback transition可重跑。

### Phase 2: Bootstrap and reference alignment

**File: `setup/templates/path-policy.json`**

#### 2a. 新增 compatibility default template (~40 lines)

**File: `setup/init.sh`**

#### 2b. 支援 optional policy source、原子驗證替換並避免 custom layout 時建立固定 spec tree (~90 net lines)

若 target 已有 policy 或第二參數提供 policy，保留 custom layout；否則安裝 default template 並保留舊目錄初始化。

**Files: `CLAUDE.md`, `setup/AGENT_SETUP_PROTOCOL.md`, `docs/01-method-architecture.md`, `docs/02-canonical-spec.md`, `docs/03-change-management.md`, `docs/06-anti-fake-test.md`, `docs/09-agent-cli-evaluation.md`, `docs/10-claude-code-implementation.md`, `docs/11-headroom-context.md`, `docs/12-ai-agent-readiness-gate.md`, `.claude/agents/red-verifier.md`, `setup/templates/managed-settings.json`**

#### 2c. 把 normative 固定資料夾敘述改成 policy contract，保留 default examples (~200 changed lines)

移除 managed settings 的 fixed spec deny，由 configured protected-spec hook 執行 project-local enforcement；`.git/` 與 hook protection 不變。
Machine-wide managed settings 只提供 permission hardening；不註冊 repository-relative hooks，也不啟用 `allowManagedHooksOnly`。Runtime hooks 維持 target-reviewed、project-scoped registration，避免 trust elevation。

**Tests for Phase 2:**

- default init 在 temp target 產生相容目錄與 `.vdd/path-policy.json`。
- custom init 不額外建立 `specs/`，且 smoke test 使用 custom implementation root。
- 文件中的 normative gate 敘述與設定 key 一致。

### Phase 3: Strict verification and rollback evidence

**Files: working tree**

#### 3a. 執行 targeted、related suite、static syntax 與 governance bundle (~0 product lines)

在 isolated virtualenv 安裝 `requirements-governance.txt`，執行 hook tests、完整 unittest、governance validate、render check、py_compile 與 `git diff --check`。

#### 3b. 獨立 review 並修正 critical/major findings (~300 lines)

依 Strict profile 與 Hermes cross-file gate，由獨立 context 檢查 path escape、fail-open、backward compatibility 與 bootstrap/document drift。

**Tests for Phase 3:**

- 所有 Phase 1/2 tests 綠。
- validator 與 deterministic render 綠。
- independent review 無 unresolved critical；major 若不修必明列理由。
- rollback dry-run 證明刪除 target policy 即回復 compatibility defaults，無 data migration。

## Integration Issues & Edge Cases

1. **Absolute tool path**：先 realpath 再轉 repository-relative；repository 外路徑不套用 target policy。
2. **Nested modules with duplicate stems**：custom policy 可用 `{relative}` 或 `{path}` 避免同名 spec/evidence collision；default 保留舊 `{module}` 行為。
3. **Malformed local policy**：任何 hook 都 loud fail，避免 typo 讓 protected paths 失效。
4. **Policy self-protection**：managed permissions、Edit/Write hook 與 Bash guard 都保護 `.vdd/path-policy.json`、hook code 與 project hook registration，避免 agent 改寫 enforcement boundary。
5. **Bash syntax coverage**：延續 deterministic bypass patterns，根路徑會 regex escape；mutating command 含 shell expansion 時 fail closed，不宣稱完整 shell parser。
6. **Custom test stack**：`green_commands` 是 argv arrays，不需要 pytest/ruff；空 command list 不允許，避免 GREEN 無驗證。
7. **Command trust**：project policy／hooks 在信任 repository 時由人 review，執行期間由 managed permissions 與 hooks 自我保護；RED/GREEN executable 必須 allowlist，禁止 shell trampoline/Python `-c*`，輸出限制且遮蔽常見 secrets。
8. **Authority boundary**：不修改 manifest authority、canonical pipeline 或 cutover preconditions。

## Files Changed Summary

| File | Phase | Changes |
|---|---:|---|
| `.claude/hooks/path_policy.py` | 1 | NEW — shared policy loader and matchers |
| `.claude/hooks/run_policy_command.py` | 1 | NEW — shell-free RED argv runner with timeout/output controls |
| `.plans/configurable-path-policy.md` | 1-3 | NEW — design, rollout, rollback, verification plan |
| `.claude/hooks/{pre_impl_gate,bash_guard,green_gate,inject_spec,reinject_rules,test_weakening_guard}.py` | 1 | consume/reinject configured paths/commands |
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
| `.claude/agents/red-verifier.md` | 2 | configured test/implementation guidance |
| `setup/templates/managed-settings.json` | 2 | protect control plane, remove fixed spec-folder deny, keep hooks project-scoped |

**Total new product/config code**: ~850 lines / **Total test code**: ~800 lines

## Rollout Plan

1. Merge Phase 1 with policy absent by default in existing targets; validate compatibility defaults and custom temp target.
2. Merge Phase 2 template/bootstrap/docs; new targets receive default policy，custom targets may provide policy before init or as init argument 2.
3. Run Phase 3 Strict gate; rollout remains repository-only and non-authoritative. Rollback is `git revert` plus removal of target `.vdd/path-policy.json`; no schema/data migration or authority cutover is involved.

Each phase is independently mergeable and testable.
