# Governance shadow canonical

This directory is the repository-side shadow created for `MCR:2026:004`.

Current state: **Notion remains canonical.** These files are non-authoritative until every cutover precondition in `manifest.yaml` passes and the Methodology Warden explicitly approves cutover.

## Loading contract

1. Read `manifest.yaml` for authority state and the frozen five-gate order.
2. Load only the task-relevant registry, gate, and profile files.
3. Load `docs/` and dated assessments only when implementation or historical context is needed.

## Validation

```bash
pip install -r requirements-governance.txt
python scripts/governance.py validate
python scripts/governance.py render --check
python -m unittest discover -s tests -v
```

`generated/notion-canonical-view.md` is deterministic output. Edit source YAML instead of editing the generated file.

## Cutover safety

- No file in this directory changes the current authority by its existence alone.
- `GATE:ADMIT` is upstream and `GATE:REGRESSION` is auxiliary; neither is a sixth pipeline gate.
- A mismatch must fail loudly. It must never silently choose one source during the comparison phase.
- Cutover requires a separate explicit human decision after schema, reference, conformance, generation, rollback, and observation requirements are satisfied.
