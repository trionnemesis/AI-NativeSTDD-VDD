import copy
import importlib.util
import tempfile
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

    def test_skill_runtime_projections_are_deterministic_and_current(self):
        first = governance_script.render_skill_projections(ROOT)
        second = governance_script.render_skill_projections(ROOT)
        expected = {
            Path(".claude") / "skills" / source.parent.name / "SKILL.md"
            for source in (ROOT / "skills").glob("*/SKILL.md")
        }
        self.assertEqual(first, second)
        self.assertEqual(set(first), expected)
        for relative_path, rendered in first.items():
            self.assertEqual((ROOT / relative_path).read_text(encoding="utf-8"), rendered)
        self.assertEqual(governance_script.skill_projection_drift(ROOT), [])

    def test_skill_projection_drift_check_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "skills" / "example" / "SKILL.md"
            source.parent.mkdir(parents=True)
            source.write_text("---\nname: example\n---\n\n# Example\n", encoding="utf-8")

            self.assertTrue(governance_script.skill_projection_drift(root))
            governance_script.write_skill_projections(root)
            self.assertEqual(governance_script.skill_projection_drift(root), [])

            runtime_projection = root / ".claude" / "skills" / "example" / "SKILL.md"
            runtime_projection.write_text("stale\n", encoding="utf-8")
            self.assertTrue(governance_script.skill_projection_drift(root))

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
        required_paths = {"AGENTS.md", "CLAUDE.md", "skills/**", ".claude/skills/**"}
        for event in ("pull_request", "push"):
            self.assertTrue(
                required_paths.issubset(set(workflow["on"][event]["paths"])),
                f"{event} path filters do not cover all agent instruction surfaces",
            )
        self.assertEqual(workflow["permissions"]["contents"], "read")
        self.assertIn("validate", workflow["jobs"])
        setup_python = workflow["jobs"]["validate"]["steps"][1]
        self.assertEqual(setup_python["with"]["cache-dependency-path"], "requirements-governance.txt")
        run_steps = {
            step["run"]
            for step in workflow["jobs"]["validate"]["steps"]
            if "run" in step
        }
        self.assertIn("python scripts/governance.py render-skills --check", run_steps)


if __name__ == "__main__":
    unittest.main()
