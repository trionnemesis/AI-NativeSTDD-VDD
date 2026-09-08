#!/usr/bin/env python3
# Why: GREEN Gate — Stop hook。configured verification commands 全數通過才允許結束。
# 環境未就緒、runner 錯誤與 verification failure 都必須 block；
# 區分的是診斷資訊，不是強制等級。
import json
import os
import selectors
import subprocess
import sys
import time
from collections import namedtuple

from path_policy import PolicyError, load_policy, project_root

COMMAND_TIMEOUT_SECONDS = 300
PROBE_TIMEOUT_SECONDS = 60
OUTPUT_TAIL_BYTES = 2000
COMMAND_ECHO_CHARS = 300
READ_CHUNK_BYTES = 65536
POLL_SECONDS = 1.0
SETUP_REFERENCE = "setup/AGENT_SETUP_PROTOCOL.md §2 P5"
ENVIRONMENT_NOTE = (
    "  這是環境錯誤，不是 verification failure；gate 仍然 block。\n"
    f"  修復：{SETUP_REFERENCE}。"
)
# exit code 無法判定「跑了多少」，所以不得宣稱沒有斷言執行過。
# 借用 docs/05 GATE:VDD 既有語意：INCONCLUSIVE 不得當作 PASS。
INCONCLUSIVE_NOTE = (
    "  此結果 INCONCLUSIVE：exit code 無法判定檢查結論，且可能已有部分測試執行；\n"
    "  依 GATE:VDD 語意 INCONCLUSIVE 不得當作 PASS，gate 仍然 block。"
)

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


def decode_tail(tail, total):
    text = bytes(tail).decode("utf-8", "replace").strip()
    if not text:
        return "<no output>"
    if total > OUTPUT_TAIL_BYTES:
        return "…（前段省略）\n" + text
    return text


def capture(command, timeout, cwd):
    """執行命令，串流讀取且只保留有上限的輸出尾段。

    輸出永遠不會整份進入記憶體或磁碟，因此吵雜的 suite 無法拖垮 hook 或 host。
    returncode 為 None 代表逾時。
    """
    deadline = time.monotonic() + timeout
    tail = bytearray()
    total = 0
    timed_out = False

    with subprocess.Popen(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ) as proc:
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                if not selector.select(min(remaining, POLL_SECONDS)):
                    continue
                chunk = os.read(proc.stdout.fileno(), READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                tail += chunk
                if len(tail) > OUTPUT_TAIL_BYTES:
                    del tail[: len(tail) - OUTPUT_TAIL_BYTES]
        finally:
            selector.close()

        if not timed_out:
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
        if timed_out:
            proc.kill()
            proc.wait()

    returncode = None if timed_out else proc.returncode
    return Captured(returncode, decode_tail(tail, total))


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
            f"{INCONCLUSIVE_NOTE}"
        )
    if result.returncode is None:
        return (
            f"{header} VERIFICATION_ERROR：命令逾時（{COMMAND_TIMEOUT_SECONDS}s）。\n"
            f"{INCONCLUSIVE_NOTE}\n  output:\n{result.tail}"
        )
    if result.returncode == 0:
        return None

    meaning = check["exit_meanings"].get(result.returncode, "UNKNOWN")
    verdict = (
        "VERIFICATION_FAILED"
        if result.returncode in check["failure_exit_codes"]
        else "VERIFICATION_ERROR"
    )
    note = "" if verdict == "VERIFICATION_FAILED" else f"\n{INCONCLUSIVE_NOTE}"
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
