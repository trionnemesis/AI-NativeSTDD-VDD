# Governance shadow canonical

This directory is the repository-side machine-readable shadow created for `MCR:2026:004`.

Current authority remains **Notion canonical**. The Notion workspace now exposes a human-only main structure:

- [Human Handbook](https://app.notion.com/p/3a2f5b2d1a9081f7a93ff2af3a6933a9)
- [Archive of legacy technical, Agent, and governance pages](https://app.notion.com/p/399f5b2d1a9081afbeb3d7c07cabe014)

The reviewed Archive semantic projection is stored in [`reconciliation/notion-archive-baseline.yaml`](reconciliation/notion-archive-baseline.yaml). Phase 2 compares that frozen baseline with the repository projection and produces [`generated/semantic-reconciliation-report.md`](../generated/semantic-reconciliation-report.md).

## Loading contract

1. Read `manifest.yaml` for authority state and the frozen five-gate order.
2. Load only the task-relevant registry, Gate, profile, and policy files.
3. Use the Human Handbook for explanation; use the Archive only for audit, reconciliation, or rollback work.
4. Load `docs/` and dated assessments only when implementation or historical context is needed.

## Validation

```bash
pip install -r requirements-governance.txt
python scripts/governance.py validate
python scripts/governance.py render --check
python scripts/semantic_reconcile.py validate
python scripts/semantic_reconcile.py render --check
python scripts/codex_adapter.py validate
python -m unittest discover -s tests -v
```

`generated/notion-canonical-view.md` and `generated/semantic-reconciliation-report.md` are deterministic output. Edit source YAML instead of editing generated files.

## Phase 2 result

- Semantic surface: fixed pipeline, Gate boundaries, Stable ID canonical terms, namespaces, Gate assertion keys, System/Change Profiles, mandatory controls, and frozen invariants.
- Result: `SEMANTIC_MATCH` for `RECON:2026:001`.
- Authority: unchanged (`NOTION_CANONICAL` / `SHADOW_NON_AUTHORITATIVE` / `pending`).
- Remaining before cutover: rollback dry run, observation window, and explicit Methodology Warden approval.

## Cutover safety

- No file in this directory changes authority by its existence alone.
- `GATE:ADMIT` is upstream and `GATE:REGRESSION` is auxiliary; neither is a sixth pipeline Gate.
- A mismatch must fail loudly. It must never silently choose one source during reconciliation.
- Cutover requires a separate explicit human decision after schema, reference, conformance, generation, rollback, and observation requirements are satisfied.
