import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "semantic_reconcile",
    ROOT / "scripts" / "semantic_reconcile.py",
)
semantic_reconcile = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(semantic_reconcile)


class SemanticReconciliationTests(unittest.TestCase):
    def test_archive_baseline_matches_repository_projection(self):
        result = semantic_reconcile.validate_reconciliation(ROOT)
        self.assertEqual(result["status"], "SEMANTIC_MATCH")
        self.assertEqual(result["expected_digest"], result["actual_digest"])
        self.assertEqual(result["differences"], [])

    def test_pipeline_order_drift_is_detected(self):
        baseline = semantic_reconcile.load_yaml(
            ROOT / "governance" / "reconciliation" / "notion-archive-baseline.yaml"
        )["semantic_contract"]
        actual = semantic_reconcile.extract_repo_semantics(ROOT)
        changed = copy.deepcopy(actual)
        changed["canonical_pipeline"] = list(reversed(changed["canonical_pipeline"]))
        diffs = semantic_reconcile.compare_contracts(baseline, changed)
        self.assertTrue(any("canonical_pipeline" in diff for diff in diffs))

    def test_gate_assertion_drift_is_detected(self):
        baseline = semantic_reconcile.load_yaml(
            ROOT / "governance" / "reconciliation" / "notion-archive-baseline.yaml"
        )["semantic_contract"]
        actual = semantic_reconcile.extract_repo_semantics(ROOT)
        changed = copy.deepcopy(actual)
        changed["gates"]["GATE:GREEN"]["assertions"].remove("protected_tests_unmodified")
        diffs = semantic_reconcile.compare_contracts(baseline, changed)
        self.assertTrue(any("GATE:GREEN.assertions" in diff for diff in diffs))

    def test_authority_remains_notion_after_phase2(self):
        manifest = semantic_reconcile.load_yaml(ROOT / "governance" / "manifest.yaml")
        self.assertEqual(manifest["authority"]["current"], "NOTION_CANONICAL")
        self.assertEqual(manifest["authority"]["repository_state"], "SHADOW_NON_AUTHORITATIVE")
        self.assertEqual(manifest["authority"]["cutover_decision"], "pending")
        self.assertTrue(manifest["semantic_reconciliation"]["authority_unchanged"])
        self.assertFalse(manifest["cutover_preconditions"]["rollback_dry_run_pass"])
        self.assertFalse(manifest["cutover_preconditions"]["observation_window_defined"])
        self.assertFalse(manifest["cutover_preconditions"]["explicit_human_cutover_approval"])

    def test_generated_report_is_deterministic_and_current(self):
        first = semantic_reconcile.render_markdown(ROOT)
        second = semantic_reconcile.render_markdown(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(
            (ROOT / "generated" / "semantic-reconciliation-report.md").read_text(encoding="utf-8"),
            first,
        )


if __name__ == "__main__":
    unittest.main()
