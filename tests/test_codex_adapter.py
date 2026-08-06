import copy
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_adapter", ROOT / "scripts" / "codex_adapter.py")
adapter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(adapter)


class CodexAdapterTests(unittest.TestCase):
    def setUp(self):
        self.mapping = adapter.load_yaml(adapter.ADAPTER)

    def test_adapter_is_valid_against_current_governance(self):
        summary = adapter.validate_adapter(self.mapping, ROOT)
        self.assertEqual(summary["pipeline_gates"], 5)
        self.assertEqual(summary["delivery_lanes"], 4)

    def test_l5_is_overlay_not_a_pipeline_gate(self):
        self.assertTrue(self.mapping["lanes"]["L5-long-task-overlay"]["overlay_only"])
        self.assertEqual(self.mapping["lanes"]["L5-long-task-overlay"]["delivery_gates"], [])

    def test_unknown_gate_is_rejected(self):
        changed = copy.deepcopy(self.mapping)
        changed["lanes"]["L2-feature"]["delivery_gates"].append("GATE:UNKNOWN")
        with self.assertRaises(adapter.AdapterValidationError):
            adapter.validate_adapter(changed, ROOT)

    def test_authority_must_match_manifest(self):
        changed = copy.deepcopy(self.mapping)
        changed["authority"]["required_current"] = "REPOSITORY_CANONICAL"
        with self.assertRaises(adapter.AdapterValidationError):
            adapter.validate_adapter(changed, ROOT)

    def test_repository_manifest_pipeline_must_remain_frozen(self):
        manifest_path = ROOT / "governance" / "manifest.yaml"
        original = adapter.load_yaml(manifest_path)
        with tempfile.TemporaryDirectory() as tmp:
            changed_root = Path(tmp)
            (changed_root / "governance").mkdir(exist_ok=True)
            shutil.copy(manifest_path, changed_root / "governance" / "manifest.yaml")
            shutil.copytree(ROOT / "governance" / "profiles", changed_root / "governance" / "profiles")
            changed = copy.deepcopy(original)
            changed["canonical_pipeline"].append("GATE:UNKNOWN")
            (changed_root / "governance" / "manifest.yaml").write_text(
                yaml.safe_dump(changed, sort_keys=False), encoding="utf-8"
            )
            with self.assertRaises(adapter.AdapterValidationError):
                adapter.validate_adapter(self.mapping, changed_root)

    def test_render_is_deterministic_and_mentions_codex_review(self):
        first = adapter.render(self.mapping)
        second = adapter.render(self.mapping)
        self.assertEqual(first, second)
        self.assertIn("codex exec", first)
        self.assertIn("L5-long-task-overlay", first)


if __name__ == "__main__":
    unittest.main()
