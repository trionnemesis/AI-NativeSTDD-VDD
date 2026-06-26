import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_hook(script, cwd, payload, env=None):
    return subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def write_feature(base, name="test"):
    spec = base / "specs" / "features" / f"{name}.feature"
    spec.parent.mkdir(parents=True)
    spec.write_text(f"Feature: {name}\n")


def write_phase(base, phase):
    phase_file = base / ".vdd" / "phase"
    phase_file.parent.mkdir(parents=True)
    phase_file.write_text(phase)


def write_red_evidence(base, name="test"):
    red_file = base / ".vdd" / "red" / f"{name}.json"
    red_file.parent.mkdir(parents=True)
    red_file.write_text(
        json.dumps(
            {
                "requirement_id": name,
                "test_name": f"test_{name}",
                "baseline_commit_sha": "abc123",
                "failure_message": "AssertionError: missing implementation",
                "failure_location": "tests/test_test.py:1",
                "execution_timestamp": "2026-06-26T00:00:00Z",
                "failure_category": "missing_implementation",
            }
        )
    )


class HookTests(unittest.TestCase):
    def test_pre_impl_gate_blocks_when_phase_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_feature(base)

            result = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": "src/test.py"}},
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("GATE:RED", result.stderr)

    def test_pre_impl_gate_requires_red_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_feature(base)
            write_phase(base, "RED_VERIFIED")

            result = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": "src/test.py"}},
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn(".vdd/red/test.json", result.stderr)

    def test_pre_impl_gate_accepts_valid_red_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_feature(base)
            write_phase(base, "RED_VERIFIED")
            write_red_evidence(base)

            result = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": "src/test.py"}},
            )

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")

    def test_bash_guard_blocks_src_write_even_without_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hook(
                ".claude/hooks/bash_guard.py",
                Path(tmp),
                {"tool_name": "Bash", "tool_input": {"command": "echo x > src/test.py"}},
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("GATE:RED/BASH", result.stderr)

    def test_green_gate_blocks_missing_ruff_as_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            os.symlink(sys.executable, bin_dir / "python3")
            env = {**os.environ, "PATH": str(bin_dir)}
            tests_dir = base / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_smoke.py").write_text("def test_smoke():\n    assert 1 == 1\n")

            result = run_hook(".claude/hooks/green_gate.py", base, {}, env=env)

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("ruff", payload["reason"])

    def test_green_gate_does_not_promote_init_to_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            for command in ("python3", "ruff"):
                script = bin_dir / command
                script.write_text("#!/bin/sh\nexit 0\n")
                script.chmod(script.stat().st_mode | stat.S_IXUSR)
            env = {**os.environ, "PATH": str(bin_dir)}
            write_phase(base, "INIT")

            result = run_hook(".claude/hooks/green_gate.py", base, {}, env=env)

            self.assertEqual(result.returncode, 0)
            self.assertEqual((base / ".vdd" / "phase").read_text(), "INIT")

    def test_test_weakening_guard_blocks_assert_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            test_file = base / "tests" / "test_bad.py"
            test_file.parent.mkdir()
            test_file.write_text("def test_bad():\n    assert True\n")

            result = run_hook(
                ".claude/hooks/test_weakening_guard.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": str(test_file)}},
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("assert True", result.stderr)


if __name__ == "__main__":
    unittest.main()
