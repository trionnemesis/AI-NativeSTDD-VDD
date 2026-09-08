import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_SPEC = importlib.util.spec_from_file_location(
    "path_policy", ROOT / ".claude" / "hooks" / "path_policy.py"
)
PATH_POLICY = importlib.util.module_from_spec(POLICY_SPEC)
POLICY_SPEC.loader.exec_module(PATH_POLICY)
sys.modules.setdefault("path_policy", PATH_POLICY)
GREEN_GATE_SPEC = importlib.util.spec_from_file_location(
    "green_gate", ROOT / ".claude" / "hooks" / "green_gate.py"
)
GREEN_GATE = importlib.util.module_from_spec(GREEN_GATE_SPEC)
GREEN_GATE_SPEC.loader.exec_module(GREEN_GATE)


def synthetic_check(
    label, probe_exit, command_exit, command_output="", output_size=0
):
    # output_size 讓子行程「產生」大量輸出，而不是把它塞進 argv（會撞 ARG_MAX）。
    def script(exit_code, output, size=0):
        emit = f"sys.stdout.write({output!r})\n" if output else ""
        if size:
            emit += f'sys.stdout.write("x" * {size})\n'
        return "import sys\n" + emit + f"sys.exit({exit_code})\n"

    return {
        "label": label,
        "probe": [sys.executable, "-I", "-c", script(probe_exit, "")],
        "command": [
            sys.executable,
            "-I",
            "-c",
            script(command_exit, command_output, output_size),
        ],
        "failure_exit_codes": {1},
        "exit_meanings": {1: "TESTS_FAILED", 2: "INTERRUPTED"},
    }


HOOK_TIMEOUT_SECONDS = 60


def run_hook(script, cwd, payload, env=None):
    # CLAUDE_PROJECT_DIR 必須釘在 fixture 上。若讓 ambient 值漏進來，hook 會把真正的
    # repository 當成 project root，讀錯 policy，而 green_gate 更會再跑一次本檔的
    # 測試而無限遞迴。timeout 讓這類問題 loud fail，而不是掛住。
    if env is None:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(cwd)}
    return subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=HOOK_TIMEOUT_SECONDS,
        check=False,
    )


def run_init(target, policy_source=None):
    fake_bin = target.parent / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    python3 = fake_bin / "python3"
    pip_log = target.parent / "pip.log"
    python3.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then\n'
        "  shift 2\n"
        f"  printf '%s\\n' \"$*\" >> {shlex.quote(str(pip_log))}\n"
        "  exit 0\n"
        "fi\n"
        f"exec {shlex.quote(sys.executable)} \"$@\"\n"
    )
    python3.chmod(python3.stat().st_mode | stat.S_IXUSR)
    command = ["bash", str(ROOT / "setup" / "init.sh"), str(target)]
    if policy_source is not None:
        command.append(str(policy_source))
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        env={**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
    )


def write_policy(base, **overrides):
    path = base / ".vdd" / "path-policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides))


def write_feature(base, path="specs/features/test.feature"):
    feature = base / path
    feature.parent.mkdir(parents=True, exist_ok=True)
    feature.write_text("Feature: test\n")


def write_phase_and_evidence(base, evidence=".vdd/red/test.json"):
    phase = base / ".vdd" / "phase"
    phase.parent.mkdir(parents=True, exist_ok=True)
    phase.write_text("RED_VERIFIED")
    evidence_path = base / evidence
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(
            {
                "requirement_id": "REQ:TEST",
                "test_name": "test_example",
                "baseline_commit_sha": "abc123",
                "failure_message": "AssertionError",
                "failure_location": "tests/test_example.py:1",
                "execution_timestamp": "2026-07-14T00:00:00Z",
                "failure_category": "missing_implementation",
            }
        )
    )


class HookTests(unittest.TestCase):
    def test_default_policy_template_matches_runtime_defaults(self):
        template = json.loads(
            (ROOT / "setup" / "templates" / "path-policy.json").read_text()
        )
        self.assertEqual(template, PATH_POLICY.DEFAULT_POLICY)

    def test_policy_reference_documents_cover_every_runtime_key(self):
        reference = (ROOT / "docs" / "10-claude-code-implementation.md").read_text()
        for key in PATH_POLICY.DEFAULT_POLICY:
            with self.subTest(key=key):
                self.assertIn(f"`{key}`", reference)

    def test_claude_adapter_requires_confirm_mode_for_every_task(self):
        adapter = (ROOT / "CLAUDE.md").read_text()
        protocol = (ROOT / "setup" / "AGENT_SETUP_PROTOCOL.md").read_text()
        confirm_action = next(
            line
            for line in adapter.splitlines()
            if line.startswith("4.") and "Confirm Mode" in line
        )

        self.assertIn("任何新任務", confirm_action)
        self.assertIn("任何新任務", protocol)

    def test_default_pre_impl_gate_preserves_existing_red_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_feature(base)
            missing_phase = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": "src/test.py"}},
            )
            write_phase_and_evidence(base)
            accepted = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": "src/test.py"}},
            )

            self.assertEqual(missing_phase.returncode, 2)
            self.assertIn("GATE:RED", missing_phase.stderr)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_pre_impl_gate_supports_custom_nested_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(
                base,
                implementation_roots=["app"],
                feature_spec_templates=["requirements/features/{relative}.feature"],
                protected_spec_roots=["requirements"],
                red_evidence_template=".evidence/red/{relative}.json",
                spec_change_paths=["requirements"],
            )
            write_feature(base, "requirements/features/services/login.feature")
            write_phase_and_evidence(base, ".evidence/red/services/login.json")

            custom = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "app/services/login.py"},
                },
            )
            unconfigured = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {"tool_name": "Edit", "tool_input": {"file_path": "src/test.py"}},
            )
            protected = run_hook(
                ".claude/hooks/pre_impl_gate.py",
                base,
                {
                    "tool_name": "Edit",
                    "tool_input": {"file_path": "requirements/login.feature"},
                },
            )

            self.assertEqual(custom.returncode, 0, custom.stderr)
            self.assertEqual(unconfigured.returncode, 0, unconfigured.stderr)
            self.assertEqual(protected.returncode, 2)
            self.assertIn("protected spec roots", protected.stderr)

    def test_hooks_fail_closed_for_invalid_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, unknown_key=True)
            for script, payload in (
                (
                    ".claude/hooks/pre_impl_gate.py",
                    {"tool_input": {"file_path": "src/test.py"}},
                ),
                (
                    ".claude/hooks/bash_guard.py",
                    {"tool_input": {"command": "echo x > src/test.py"}},
                ),
            ):
                with self.subTest(script=script):
                    result = run_hook(script, base, payload)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("PATH POLICY", result.stderr)

    def test_bash_guard_uses_configured_roots_without_substring_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(
                base,
                implementation_roots=["app"],
                protected_spec_roots=["requirements"],
            )
            for command in (
                "echo x > app/login.py",
                "sed -i '' requirements/login.feature",
            ):
                with self.subTest(command=command):
                    result = run_hook(
                        ".claude/hooks/bash_guard.py",
                        base,
                        {"tool_input": {"command": command}},
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)

            allowed = run_hook(
                ".claude/hooks/bash_guard.py",
                base,
                {"tool_input": {"command": 'echo "$VALUE" > happy.txt'}},
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_test_weakening_guard_checks_proposed_custom_test_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, test_file_patterns=["checks/*.case"])
            blocked = run_hook(
                ".claude/hooks/test_weakening_guard.py",
                base,
                {
                    "tool_input": {
                        "file_path": "checks/login.case",
                        "content": "assert True\n",
                    }
                },
            )
            unrelated = run_hook(
                ".claude/hooks/test_weakening_guard.py",
                base,
                {
                    "tool_input": {
                        "file_path": "tests/test_login.py",
                        "content": "assert True\n",
                    }
                },
            )

            self.assertEqual(blocked.returncode, 2)
            self.assertIn("assert True", blocked.stderr)
            self.assertEqual(unrelated.returncode, 0, unrelated.stderr)

    def test_inject_and_reinject_use_custom_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(
                base,
                implementation_roots=["app"],
                spec_change_paths=["requirements"],
                red_evidence_template="evidence/{path}.json",
                test_roots=["checks"],
            )
            spec = base / "requirements" / "login.md"
            spec.parent.mkdir()
            spec.write_text("v1\n")
            subprocess.run(["git", "init", "-q"], cwd=base, check=True)
            subprocess.run(["git", "add", "requirements/login.md"], cwd=base, check=True)
            spec.write_text("v2\n")

            injected = run_hook(".claude/hooks/inject_spec.py", base, {})
            reinjected = run_hook(".claude/hooks/reinject_rules.py", base, {})

            self.assertIn("requirements/login.md", injected.stdout)
            self.assertIn("implementation roots: app", reinjected.stdout)
            self.assertIn("pytest roots (checks)", reinjected.stdout)

    def test_green_gate_uses_custom_test_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, test_roots=["checks"])
            test = base / "checks" / "test_ok.py"
            test.parent.mkdir()
            test.write_text("def test_ok():\n    value = 1\n    assert value == 1\n")
            phase = base / ".vdd" / "phase"
            phase.write_text("RED_VERIFIED")

            result = run_hook(".claude/hooks/green_gate.py", base, {})

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(phase.read_text(), "GREEN")

    def test_green_gate_reports_verification_failure_with_command_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, test_roots=["checks"])
            test = base / "checks" / "test_fail.py"
            test.parent.mkdir()
            test.write_text("def test_fails():\n    value = 1\n    assert value == 2\n")
            phase = base / ".vdd" / "phase"
            phase.write_text("RED_VERIFIED")

            result = run_hook(".claude/hooks/green_gate.py", base, {})
            payload = json.loads(result.stdout)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(payload["decision"], "block")
            self.assertIn("VERIFICATION_FAILED", payload["reason"])
            self.assertNotIn("ENVIRONMENT_NOT_READY", payload["reason"])
            self.assertIn("test_fails", payload["reason"])
            self.assertEqual(phase.read_text(), "RED_VERIFIED")

    def test_green_gate_separates_environment_error_from_verification_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            missing_toolchain = GREEN_GATE.evaluate(
                synthetic_check("pytest", probe_exit=1, command_exit=0), 1, base
            )
            failed_check = GREEN_GATE.evaluate(
                synthetic_check(
                    "pytest", probe_exit=0, command_exit=1, command_output="1 failed"
                ),
                1,
                base,
            )
            passing_check = GREEN_GATE.evaluate(
                synthetic_check("pytest", probe_exit=0, command_exit=0), 1, base
            )

            self.assertIn("ENVIRONMENT_NOT_READY", missing_toolchain)
            self.assertNotIn("VERIFICATION_FAILED", missing_toolchain)
            self.assertIn("setup/AGENT_SETUP_PROTOCOL.md", missing_toolchain)

            self.assertIn("VERIFICATION_FAILED", failed_check)
            self.assertNotIn("ENVIRONMENT_NOT_READY", failed_check)
            self.assertIn("1 failed", failed_check)

            self.assertIsNone(passing_check)

    def test_green_gate_caps_captured_output_in_block_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            size = GREEN_GATE.OUTPUT_TAIL_BYTES * 100

            reason = GREEN_GATE.evaluate(
                synthetic_check(
                    "pytest", probe_exit=0, command_exit=1, output_size=size
                ),
                1,
                base,
            )

            self.assertIn("VERIFICATION_FAILED", reason)
            self.assertIn("前段省略", reason)
            # reason 長度只由「輸出尾段 + 命令回顯 + 固定文案」決定，與輸出總量無關。
            budget = (
                GREEN_GATE.OUTPUT_TAIL_BYTES + GREEN_GATE.COMMAND_ECHO_CHARS + 500
            )
            self.assertLess(len(reason), budget)
            self.assertLess(len(reason), size)

    def test_green_gate_separates_runner_error_from_red_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)

            runner_error = GREEN_GATE.evaluate(
                synthetic_check("pytest", probe_exit=0, command_exit=2), 1, base
            )
            red_tests = GREEN_GATE.evaluate(
                synthetic_check("pytest", probe_exit=0, command_exit=1), 1, base
            )

            self.assertIn("VERIFICATION_ERROR", runner_error)
            self.assertNotIn("VERIFICATION_FAILED", runner_error)
            self.assertIn("INCONCLUSIVE", runner_error)
            self.assertNotIn("沒有任何斷言", runner_error)

            self.assertIn("VERIFICATION_FAILED", red_tests)
            self.assertNotIn("VERIFICATION_ERROR", red_tests)

    def test_green_gate_treats_collection_error_as_runner_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, test_roots=["checks"])
            broken = base / "checks" / "test_broken.py"
            broken.parent.mkdir()
            broken.write_text(
                "import definitely_not_a_real_module_xyz\n\n"
                "def test_x():\n"
                "    assert definitely_not_a_real_module_xyz\n"
            )
            phase = base / ".vdd" / "phase"
            phase.write_text("RED_VERIFIED")

            result = run_hook(".claude/hooks/green_gate.py", base, {})
            payload = json.loads(result.stdout)

            self.assertEqual(payload["decision"], "block")
            self.assertIn("VERIFICATION_ERROR", payload["reason"])
            self.assertNotIn("VERIFICATION_FAILED", payload["reason"])
            self.assertIn("collection error", payload["reason"])
            self.assertEqual(phase.read_text(), "RED_VERIFIED")

    def test_hook_fixture_ignores_ambient_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, test_roots=["checks"])
            test = base / "checks" / "test_ok.py"
            test.parent.mkdir()
            test.write_text("def test_ok():\n    value = 1\n    assert value == 1\n")
            phase = base / ".vdd" / "phase"
            phase.write_text("RED_VERIFIED")

            # 模擬 Claude Code runtime：ambient CLAUDE_PROJECT_DIR 指向真正的 repo。
            with unittest.mock.patch.dict(
                os.environ, {"CLAUDE_PROJECT_DIR": str(ROOT)}
            ):
                result = run_hook(".claude/hooks/green_gate.py", base, {})

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(phase.read_text(), "GREEN")

    def test_green_gate_capture_is_bounded_while_the_command_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            volume = 20 * 1024 * 1024

            captured = GREEN_GATE.capture(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import sys\n"
                        f'sys.stdout.write("x" * {volume})\n'
                        "sys.exit(1)\n"
                    ),
                ],
                30,
                base,
            )

            self.assertEqual(captured.returncode, 1)
            self.assertIn("前段省略", captured.tail)
            # 尾段長度只受上限支配，與 20MB 的輸出總量無關。
            self.assertLess(len(captured.tail), GREEN_GATE.OUTPUT_TAIL_BYTES + 100)

    def test_green_gate_capture_times_out_without_hanging(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            started = time.monotonic()

            captured = GREEN_GATE.capture(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import sys, time\n"
                        'sys.stdout.write("started\\n")\n'
                        "sys.stdout.flush()\n"
                        "time.sleep(60)\n"
                    ),
                ],
                2,
                base,
            )

            self.assertIsNone(captured.returncode)
            self.assertIn("started", captured.tail)
            self.assertLess(time.monotonic() - started, 30)

    def test_read_isolation_guard_is_registered_for_read_tools(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        entries = settings["hooks"]["PreToolUse"]

        matched = [
            entry
            for entry in entries
            if entry.get("matcher") == "Read|Grep|Glob"
            and any(
                "read_isolation_guard.py" in hook["command"] for hook in entry["hooks"]
            )
        ]

        self.assertEqual(len(matched), 1, entries)

    def test_read_isolation_guard_blocks_tests_during_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, implementation_roots=["app"], test_roots=["checks"])
            (base / ".vdd").mkdir(exist_ok=True)
            (base / ".vdd" / "phase").write_text("RED_VERIFIED")

            for payload in (
                {"tool_name": "Read", "tool_input": {"file_path": "checks/test_a.py"}},
                {"tool_name": "Grep", "tool_input": {"path": "checks"}},
                {"tool_name": "Glob", "tool_input": {"pattern": "checks/**/*.py"}},
                {"tool_name": "Read", "tool_input": {"file_path": "app/login.spec.ts"}},
            ):
                with self.subTest(payload=payload):
                    result = run_hook(
                        ".claude/hooks/read_isolation_guard.py", base, payload
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("agent_isolation_enforced", result.stderr)
                    self.assertIn("lane=implementation", result.stderr)

            # 實作側自己的檔案、Canonical Spec 與非測試路徑都必須維持可讀。
            # 已知 over-match：實作側檔名含 test／spec 者會被預設 pattern 判為測試，
            # 解法是收窄 test_file_patterns，見
            # test_read_isolation_guard_honours_narrowed_test_file_patterns。
            for payload in (
                {"tool_name": "Read", "tool_input": {"file_path": "app/login.py"}},
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "specs/features/login.feature"},
                },
                {"tool_name": "Read", "tool_input": {"file_path": "README.md"}},
                # configured roots 之外不猜：檔名含 spec 的文件不得被當成測試擋掉。
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "docs/02-canonical-spec.md"},
                },
            ):
                with self.subTest(payload=payload):
                    result = run_hook(
                        ".claude/hooks/read_isolation_guard.py", base, payload
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_isolation_guard_honours_narrowed_test_file_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(
                base,
                implementation_roots=["app"],
                test_roots=["checks"],
                test_file_patterns=["*.spec.ts"],
            )
            (base / ".vdd").mkdir(exist_ok=True)
            (base / ".vdd" / "phase").write_text("RED_VERIFIED")

            # 預設 *test* pattern 會把這支實作誤判成測試；收窄 policy 是既有的解法。
            allowed = run_hook(
                ".claude/hooks/read_isolation_guard.py",
                base,
                {"tool_name": "Read", "tool_input": {"file_path": "app/testing.py"}},
            )
            blocked = run_hook(
                ".claude/hooks/read_isolation_guard.py",
                base,
                {"tool_name": "Read", "tool_input": {"file_path": "app/login.spec.ts"}},
            )

            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(blocked.returncode, 2, blocked.stderr)

    def test_read_isolation_guard_blocks_implementation_during_test_authoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, implementation_roots=["app"], test_roots=["checks"])
            (base / ".vdd").mkdir(exist_ok=True)
            (base / ".vdd" / "phase").write_text("INIT")

            blocked = run_hook(
                ".claude/hooks/read_isolation_guard.py",
                base,
                {"tool_name": "Read", "tool_input": {"file_path": "app/login.py"}},
            )
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            self.assertIn("lane=test_authoring", blocked.stderr)

            # 這一側必須讀得到測試與 spec，否則寫不出測試。
            for payload in (
                {"tool_name": "Read", "tool_input": {"file_path": "checks/test_a.py"}},
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "specs/features/login.feature"},
                },
            ):
                with self.subTest(payload=payload):
                    result = run_hook(
                        ".claude/hooks/read_isolation_guard.py", base, payload
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_isolation_guard_defaults_to_test_authoring_without_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, implementation_roots=["app"], test_roots=["checks"])

            result = run_hook(
                ".claude/hooks/read_isolation_guard.py",
                base,
                {"tool_name": "Read", "tool_input": {"file_path": "app/login.py"}},
            )

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("lane=test_authoring", result.stderr)

    def test_bash_guard_blocks_reading_the_isolated_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_policy(base, implementation_roots=["app"], test_roots=["checks"])
            (base / ".vdd").mkdir(exist_ok=True)
            phase = base / ".vdd" / "phase"

            phase.write_text("RED_VERIFIED")
            for command in (
                "cat checks/test_a.py",
                "head -n 20 checks/test_a.py",
                "sed -n '1,5p' checks/test_a.py",
                "grep -rn assert checks/",
            ):
                with self.subTest(phase="RED_VERIFIED", command=command):
                    result = run_hook(
                        ".claude/hooks/bash_guard.py",
                        base,
                        {"tool_input": {"command": command}},
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
            allowed = run_hook(
                ".claude/hooks/bash_guard.py",
                base,
                {"tool_input": {"command": "cat app/login.py"}},
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

            phase.write_text("INIT")
            blocked = run_hook(
                ".claude/hooks/bash_guard.py",
                base,
                {"tool_input": {"command": "cat app/login.py"}},
            )
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            allowed = run_hook(
                ".claude/hooks/bash_guard.py",
                base,
                {"tool_input": {"command": "cat checks/test_a.py"}},
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_setup_protocol_documents_the_read_side_guard(self):
        protocol = (ROOT / "setup" / "AGENT_SETUP_PROTOCOL.md").read_text()

        self.assertIn("CM-08", protocol)
        self.assertIn("read_isolation_guard.py", protocol)
        self.assertIn("8 個 .py 檔案", protocol)
        self.assertEqual(
            len(list((ROOT / ".claude" / "hooks").glob("*.py"))),
            8,
        )

    def test_managed_settings_remove_fixed_folder_and_agent_restrictions(self):
        managed = json.loads(
            (ROOT / "setup" / "templates" / "managed-settings.json").read_text()
        )
        deny = managed["permissions"]["deny"]
        self.assertFalse(any("spec" in rule for rule in deny))
        self.assertNotIn("Agent(*)", deny)
        self.assertNotIn("allowManagedHooksOnly", managed)

        project = json.loads((ROOT / ".claude" / "settings.json").read_text())
        self.assertIn(
            "test_weakening_guard.py",
            json.dumps(project["hooks"]["PreToolUse"]),
        )

    def test_project_hook_launcher_works_from_subdirectory(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
        command = settings["hooks"]["PreToolUse"][1]["hooks"][0]["command"]
        result = subprocess.run(
            command,
            cwd=ROOT / "docs",
            input=json.dumps({"tool_input": {"file_path": "README.md"}}),
            capture_output=True,
            text=True,
            shell=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)},
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_installs_default_policy_and_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            result = run_init(target)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / "specs" / "features").is_dir())
            self.assertTrue((target / ".claude" / "agents" / "red-verifier.md").is_file())
            self.assertEqual(
                (target / "AGENTS.md").read_text(),
                (ROOT / "AGENTS.md").read_text(),
            )
            self.assertEqual(
                json.loads((target / ".vdd" / "path-policy.json").read_text()),
                PATH_POLICY.DEFAULT_POLICY,
            )

    def test_init_preserves_custom_layout_and_state_on_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            source = base / "custom.json"
            source.write_text(
                json.dumps(
                    {
                        "implementation_roots": ["app"],
                        "feature_spec_templates": ["requirements/{module}.feature"],
                        "protected_spec_roots": ["requirements"],
                        "test_roots": ["checks"],
                        "spec_change_paths": ["requirements"],
                    }
                )
            )
            first = run_init(target, source)
            (target / "AGENTS.md").write_text("# Project-specific agent policy\n")
            (target / ".vdd" / "phase").write_text("RED_VERIFIED")
            sentinel = target / ".vdd" / "sentinel"
            sentinel.write_text("keep")
            second = run_init(target, target / ".vdd" / "path-policy.json")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse((target / "specs").exists())
            self.assertEqual((target / ".vdd" / "phase").read_text(), "RED_VERIFIED")
            self.assertEqual(sentinel.read_text(), "keep")
            self.assertEqual(
                (target / "AGENTS.md").read_text(),
                "# Project-specific agent policy\n",
            )
            self.assertEqual(
                (target / "AGENTS.stdd-vdd.md").read_text(),
                (ROOT / "AGENTS.md").read_text(),
            )
            self.assertIn("validated in place", second.stdout)

    def test_init_rejects_invalid_policy_without_replacing_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            existing = target / ".vdd" / "path-policy.json"
            existing.parent.mkdir(parents=True)
            original = json.dumps({"implementation_roots": ["app"]})
            existing.write_text(original)
            invalid = base / "invalid.json"
            invalid.write_text(json.dumps({"implementation_root": ["bad"]}))

            result = run_init(target, invalid)

            self.assertEqual(result.returncode, 1)
            self.assertIn("schema 驗證失敗", result.stderr)
            self.assertEqual(existing.read_text(), original)


if __name__ == "__main__":
    unittest.main()
