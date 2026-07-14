# 25 · Codex Adapter／Hermes Mapping Layer

> This is an opt-in, non-authoritative runtime adapter. The canonical methodology remains governed by Notion and `governance/manifest.yaml`.

## Purpose

`integrations/codex/adapter.yaml` maps the Hermes engineering lanes to this repository's change profiles, canonical delivery gates, required artifacts, and exit criteria. It gives Codex a machine-readable boundary without embedding Claude Code hooks or creating a second governance system.

The adapter does not:

- promote the repository shadow to canonical authority;
- add or reorder the five canonical gates;
- claim target-project hooks or runtime enforcement are installed;
- replace human approval for T3, security, migration, release, or waiver decisions.

## Mapping

| Hermes lane | Repository mapping | Expected output |
|---|---|---|
| `L1-bugfix` | `DEFECT` → `SPEC → RED → GREEN → VDD` | reproduction, Red Evidence, verification, residual risk |
| `L2-feature` | `FEATURE` → `SPEC → RED → GREEN → VDD → DEPLOY` | `.plans/<feature>.md`, implementation, tests, rollout evidence |
| `L3-research-decision` | decision-only; no delivery Gate is invented | research notes, independent verifier report, ADR |
| `L4-incident-RCA` | incident artifact; no delivery Gate is invented | timeline, evidence-backed root cause, prevention guard |
| `L5-long-task-overlay` | overlay on L1–L4, never a Gate | `TASK-STATE.md` with budget, heartbeat, stop condition, and next step |

## Codex execution

The adapter follows the Hermes Loop Contract: `rehydrate → route → plan → work → verify → gate → handoff`. Select exactly one L1–L4 lane; add L5 only when the long-task threshold is met.

For independent verification or the four-position review group, use a fresh `codex exec` context. The producing context must not treat its own review as independent. If `codex exec` is unavailable, report the missing independent-context capability instead of claiming compliance.

Validate the mapping before use:

```bash
python3 scripts/codex_adapter.py validate
python3 scripts/codex_adapter.py render
```

The validator checks the adapter against the current authority state, change profiles, and frozen five-gate pipeline. It does not validate whether a target project has installed hooks; that requires target-environment Confirm Mode.

## Boundary with the existing repository

This adapter is a consumer-facing integration surface. `governance/` remains the machine-readable shadow of the Notion methodology, while `CLAUDE.md` and `setup/AGENT_SETUP_PROTOCOL.md` remain the Claude Code compatibility and target setup surfaces. A future runtime can consume the YAML mapping, but it must preserve the precedence: manifest authority and canonical pipeline first, adapter references second, operator lane selection third.
