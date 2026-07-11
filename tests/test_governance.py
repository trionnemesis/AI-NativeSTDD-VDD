import copy
import importlib.util
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("governance_script", ROOT / "scripts" / "governance.py")
governance_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(governance_script)


class GovernanceShadowTests(unittest.TestCase):
    def test_shadow_bundle_validates(self):
        summary = governance_script.validate_repo(ROOT)
        self.assertEqual(summary["pipeline_gates"], 5)
        self.assertGreater(summary["terms"], 0)
        self.assertEqual(summary["gates"], 7)

    def test_sixth_pipeline_gate_is_rejected(self):
        manifest = governance_script.load_yaml(ROOT / "governance" / "manifest.yaml")
        registry = governance_script.load_yaml(ROOT / "governance" / "registries" / "gates.yaml")
        changed = copy.deepcopy(manifest)
        changed["canonical_pipeline"].insert(0, "GATE:ADMIT")
        with self.assertRaises(governance_script.GovernanceValidationError):
            governance_script.validate_pipeline_contract(changed, registry)

    def test_current_authority_is_still_notion(self):
        manifest = governance_script.load_yaml(ROOT / "governance" / "manifest.yaml")
        self.assertEqual(manifest["authority"]["current"], "NOTION_CANONICAL")
        self.assertEqual(manifest["authority"]["repository_state"], "SHADOW_NON_AUTHORITATIVE")
        self.assertEqual(manifest["authority"]["cutover_decision"], "pending")

    def test_glossary_stable_ids_are_unique(self):
        glossary = governance_script.load_yaml(ROOT / "governance" / "glossary.yaml")
        stable_ids = [entry["stable_id"] for entry in glossary.values()]
        self.assertEqual(len(stable_ids), len(set(stable_ids)))

    def test_generated_view_is_deterministic_and_current(self):
        first = governance_script.render_markdown(ROOT)
        second = governance_script.render_markdown(ROOT)
        self.assertEqual(first, second)
        self.assertEqual((ROOT / "generated" / "notion-canonical-view.md").read_text(), first)

    def test_all_yaml_files_parse(self):
        for path in (ROOT / "governance").rglob("*.yaml"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNotNone(yaml.safe_load(path.read_text()))

    def test_github_workflow_structure(self):
        workflow_path = ROOT / ".github" / "workflows" / "governance-shadow.yml"
        workflow = yaml.load(workflow_path.read_text(), Loader=yaml.BaseLoader)
        self.assertIn("pull_request", workflow["on"])
        self.assertIn("push", workflow["on"])
        self.assertIn(".github/workflows/governance-shadow.yml", workflow["on"]["pull_request"]["paths"])
        self.assertEqual(workflow["permissions"]["contents"], "read")
        self.assertIn("validate", workflow["jobs"])
        setup_python = workflow["jobs"]["validate"]["steps"][1]
        self.assertEqual(setup_python["with"]["cache-dependency-path"], "requirements-governance.txt")


if __name__ == "__main__":
    unittest.main()
