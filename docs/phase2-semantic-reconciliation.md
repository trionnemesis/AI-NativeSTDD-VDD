# Phase 2 Semantic Reconciliation

This phase reconciles the frozen Notion Archive machine-semantic baseline with the repository governance shadow.

- Authority remains `NOTION_CANONICAL`.
- Repository state remains `SHADOW_NON_AUTHORITATIVE`.
- The comparison covers glossary Stable IDs/canonical terms, namespaces, Gate identity/scope/stage/assertions, System/Change Profiles, mandatory controls, and frozen invariants.
- Human narrative, examples, dated assessments, and historical ledger prose are excluded from the machine semantic digest.

Run:

```bash
python3 scripts/semantic_reconcile.py validate
python3 scripts/semantic_reconcile.py render --check
```

A pass satisfies only the Phase 2 semantic-match precondition. Phase 3 rollback dry-run and observation-window design, followed by explicit Methodology Warden approval, remain required before authority cutover.
