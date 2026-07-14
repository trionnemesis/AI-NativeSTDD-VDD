# Codex Adapter / Hermes Mapping Layer

## Overview

建立一個 opt-in、read-only 的 Codex adapter，將 Hermes 的 L1–L5 engineering workflow 映射到本 repository 的 change profiles、canonical gates、evidence 與 exit criteria。adapter 只提供 machine-readable mapping、deterministic validation 與 human reference；預設不改變既有 Claude Code hooks、Notion authority 或五道 Gate。

## Design Principles

1. **Authority preservation** — mapping 必須引用既有 `governance/manifest.yaml`，不得創造第六道 pipeline Gate 或暗示 repository 已完成 authority cutover。
2. **Runtime neutrality** — adapter 描述 Codex 的操作對應，不新增 MCP、plugin 或 core tool footprint。
3. **Explicit applicability** — L1–L4 的 delivery applicability 與 L5 overlay 分開表達，避免把 context/task state 當成 delivery gate。
4. **Deterministic evidence** — mapping 的 schema、lane、profile、gate 與 command reference 可由 script 驗證，不能只靠 prompt。

## Architecture

```text
Codex task
   |
   v
integrations/codex/adapter.yaml
   |                 \
   v                  v
codex_adapter.py   docs/25-codex-adapter.md
   |
   v
governance/manifest.yaml + profiles + gates
```

The adapter reads the existing governance manifest as an authority boundary. It does not execute hooks, change profiles, or promote the repository shadow.

### Option A: Standalone adapter contract

- Add a small YAML contract and validator under `integrations/codex/`.
- Keep the existing governance validator focused on the Notion shadow.
- Allow future Codex tooling to consume the mapping without importing repository-specific Python internals.

### Option B: Embed Codex mappings in `governance/`

- Put runtime-specific mappings beside canonical gates and profiles.
- This would blur normative governance with an execution adapter and increase authority-boundary risk.

**Recommendation: Option A** — the adapter can be validated against the manifest while remaining a non-authoritative integration surface; this is directly testable and preserves the current repository contract.

## Configuration

`integrations/codex/adapter.yaml` is the only mapping source.

Precedence:

1. Existing `governance/manifest.yaml` authority and canonical pipeline.
2. Adapter mapping values that reference registered profiles/gates.
3. Human/operator task context; it may select a lane but may not override 1 or 2.

## Implementation Plan

### Phase 1: Machine-readable contract and validator

**File: `integrations/codex/adapter.yaml`**

#### 1a. Define runtime and lane mappings (~70 lines)

Map Hermes L1–L4 to applicable change profiles, canonical gates, required artifacts, and exit criteria. Define L5 as an overlay with `TASK-STATE.md`, budget, heartbeat, and stop condition requirements.

**File: `scripts/codex_adapter.py`**

#### 1b. Add deterministic validation (~100 lines)

Validate adapter version, runtime, lane set, gate references, profile references, authority constraints, and L5 overlay shape against current repository governance files. Expose `validate` and `render` commands.

**Tests for Phase 1:**

- Valid adapter passes and reports lane/profile/gate counts.
- Unknown gate or profile reference fails deterministically.
- Adapter cannot alter the five-gate order or Notion shadow authority.
- L5 is rejected if represented as a canonical pipeline gate.
- Render output is deterministic and current.

### Phase 2: Human mapping reference

**File: `docs/25-codex-adapter.md`**

#### 2a. Document usage and boundaries (~80 lines)

Explain lane selection, Gate applicability, Codex `codex exec` independent-context review, fallback behavior, and the distinction between adapter guidance and target-project runtime enforcement.

**File: `README.md`**

#### 2b. Add one repository surface and validation command (~12 lines)

Link the adapter documentation and show the deterministic validation command without changing the existing quick-start path.

**Tests for Phase 2:**

- README links resolve to the adapter documentation.
- Documentation states Notion authority and non-authoritative adapter status.
- Documentation names the independent-review fallback boundary.

## Integration Issues & Edge Cases

1. **Decision-only L3 work** — it does not enter the five-gate delivery pipeline; the adapter records research/verifier/ADR outputs instead of inventing a new Gate.
2. **L5 overlay** — `TASK-STATE.md` is required only when the long-task threshold is met and never becomes a pipeline gate.
3. **Missing target hooks** — the adapter may report target runtime enforcement as unavailable; it must not claim prompt rules are runtime-enforced.
4. **Authority drift** — validation fails if the manifest is no longer Notion-canonical shadow state or if the frozen pipeline changes.

## Files Changed Summary

| File | Phase | Changes |
|---|---|---|
| `.plans/codex-adapter.md` | Plan | This implementation plan |
| `integrations/codex/adapter.yaml` | 1 | NEW — Codex/Hermes mapping contract |
| `scripts/codex_adapter.py` | 1 | NEW — deterministic validator and renderer |
| `tests/test_codex_adapter.py` | 1 | NEW — mapping contract tests |
| `docs/25-codex-adapter.md` | 2 | NEW — human usage and boundary reference |
| `README.md` | 2 | Adapter surface and validation command link |

**Total new code**: ~100 lines / **Total test code**: ~80 lines

## Rollout Plan

1. Merge Phase 1 with the adapter contract, validator, and tests; validate it in CI using the existing governance dependency set.
2. Merge Phase 2 with human documentation and README discoverability.
3. Keep the adapter opt-in: consumers explicitly run `python3 scripts/codex_adapter.py validate`; no existing workflow is changed automatically.

Each phase is independently mergeable and testable.
