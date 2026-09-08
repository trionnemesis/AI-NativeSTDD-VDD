#!/usr/bin/env python3
# Why: GREEN Gate — Stop hook。configured verification commands 全數通過才允許結束。
# 環境未就緒、runner 錯誤與 verification failure 都必須 block；
# 區分的是診斷資訊，不是強制等級。
import json
import os
import subprocess
import sys
import tempfile
from collections import namedtuple

from path_policy import PolicyError, load_policy, project_root

COMMAND_TIMEOUT_SECONDS = 300
PROBE_TIMEOUT_SECONDS = 60
OUTPUT_TAIL_BYTES = 2000
COMMAND_ECHO_CHARS = 300
SETUP_REFERENCE = "setup/AGENT_SETUP_PROTOCOL.md §2 P5"
ENVIRONMENT_NOTE = (
    "  這是環境錯誤，不是 verification failure；gate 仍然 block。\n"
    f"  修復：{SETUP_REFERENCE}。"
)
RUNNER_NOTE = "  這是 runner／設定層錯誤，沒有任何斷言被執行；gate 仍然 block。"

# pytest 與 ruff 都只有一個 exit code 代表「檢查真的沒過」，其餘非零是 runner 錯誤。
PYTEST_EXITS = {
    1: "TESTS_FAILED",
    2: "INTERRUPTED（含 collection error）",
    3: "INTERNAL_ERROR",
    4: "USAGE_ERROR",
    5: "NO_TESTS_COLLECTED",
    6: "MAX_WARNINGS_ERROR",
}
RUFF_EXITS = {1: "LINT_VIOLATIONS", 2: "RUFF_ERROR"}

Captured = namedtuple("Captured", "returncode tail")


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


def read_tail(sink):
    # 只從檔案尾端讀回上限內的位元組，輸出多大都不會進 hook 的記憶體。
    sink.flush()
    size = sink.seek(0, os.SEEK_END)
    sink.seek(max(0, size - OUTPUT_TAIL_BYTES), os.SEEK_SET)
    text = sink.read().decode("utf-8", "replace").strip()
    if not text:
        return "<no output>"
    if size > OUTPUT_TAIL_BYTES:
        return "…（前段省略）\n" + text
    return text


def capture(command, timeout, cwd):
    """執行命令，只保留有上限的輸出尾段。returncode 為 None 代表逾時。"""
    with tempfile.TemporaryFile() as sink:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                timeout=timeout,
                check=False,
                stdout=sink,
                stderr=subprocess.STDOUT,
            )
        except subprocess.TimeoutExpired:
            return Captured(None, read_tail(sink))
        return Captured(completed.returncode, read_tail(sink))


def command_echo(command):
    text = " ".join(command)
    if len(text) <= COMMAND_ECHO_CHARS:
        return text
    return text[:COMMAND_ECHO_CHARS] + "…（後段省略）"


def build_checks(policy):
    # probe 使用 setup/AGENT_SETUP_PROTOCOL.md §2 P5 已宣告的 readiness command，
    # 讓「toolchain 缺失」與「檢查未通過」的判定是 deterministic，而不是比對 stderr 字串。
    return [
        {
            "label": "pytest",
            "probe": [sys.executable, "-I", "-m", "pytest", "--version"],
            "command": [
                sys.executable,
                "-I",
                "-m",
                "pytest",
                *policy["test_roots"],
                "-q",
                "-m",
                "not integration",
            ],
            "failure_exit_codes": {1},
            "exit_meanings": PYTEST_EXITS,
        },
        {
            "label": "ruff",
            "probe": [sys.executable, "-I", "-m", "ruff", "--version"],
            "command": [sys.executable, "-I", "-m", "ruff", "check", "."],
            "failure_exit_codes": {1},
            "exit_meanings": RUFF_EXITS,
        },
    ]


def evaluate(check, index, cwd):
    """回傳 block reason；None 代表該 check 通過。"""
    header = f"[GATE:GREEN] configured command #{index} ({check['label']})"

    try:
        probe = capture(check["probe"], PROBE_TIMEOUT_SECONDS, cwd)
    except OSError as exc:
        return (
            f"{header} ENVIRONMENT_NOT_READY：readiness probe 無法執行"
            f"（{type(exc).__name__}）。\n{ENVIRONMENT_NOTE}"
        )
    if probe.returncode is None:
        return (
            f"{header} ENVIRONMENT_NOT_READY：readiness probe 逾時"
            f"（{PROBE_TIMEOUT_SECONDS}s）。\n{ENVIRONMENT_NOTE}"
        )
    if probe.returncode != 0:
        return (
            f"{header} ENVIRONMENT_NOT_READY：readiness probe exit="
            f"{probe.returncode}。\n{ENVIRONMENT_NOTE}\n"
            f"  probe output:\n{probe.tail}"
        )

    try:
        result = capture(check["command"], COMMAND_TIMEOUT_SECONDS, cwd)
    except OSError as exc:
        return (
            f"{header} VERIFICATION_ERROR：命令無法執行（{type(exc).__name__}）。\n"
            f"{RUNNER_NOTE}"
        )
    if result.returncode is None:
        return (
            f"{header} VERIFICATION_ERROR：命令逾時（{COMMAND_TIMEOUT_SECONDS}s）。\n"
            f"{RUNNER_NOTE}\n  output:\n{result.tail}"
        )
    if result.returncode == 0:
        return None

    meaning = check["exit_meanings"].get(result.returncode, "UNKNOWN")
    verdict = (
        "VERIFICATION_FAILED"
        if result.returncode in check["failure_exit_codes"]
        else "VERIFICATION_ERROR"
    )
    note = "" if verdict == "VERIFICATION_FAILED" else f"\n{RUNNER_NOTE}"
    return (
        f"{header} {verdict}：exit={result.returncode}（{meaning}）。{note}\n"
        f"  command: {command_echo(check['command'])}\n"
        f"  output:\n{result.tail}"
    )


def main():
    data = json.load(sys.stdin)

    # 防止 Stop hook 遞迴呼叫自己
    if data.get("stop_hook_active"):
        return

    try:
        policy = load_policy()
        cwd = project_root()
    except PolicyError as exc:
        block(f"[PATH POLICY] {exc}")
        return

    for index, check in enumerate(build_checks(policy), start=1):
        reason = evaluate(check, index, cwd)
        if reason is not None:
            block(reason)
            return

    # 更新 phase 到 GREEN
    phase_file = cwd / ".vdd" / "phase"
    if phase_file.exists():
        try:
            current = phase_file.read_text(encoding="utf-8").strip()
            if current == "RED_VERIFIED":
                phase_file.write_text("GREEN", encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            block(f"[GATE:GREEN] 無法更新 phase：{type(exc).__name__}")


if __name__ == "__main__":
    main()
    sys.exit(0)
