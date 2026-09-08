#!/usr/bin/env python3
# Why: GREEN Gate — Stop hook。configured verification commands 全數通過才允許結束。
# 環境未就緒與 verification failure 都必須 block；區分的是診斷資訊，不是強制等級。
import json
import subprocess
import sys

from path_policy import PolicyError, load_policy, project_root

COMMAND_TIMEOUT_SECONDS = 300
PROBE_TIMEOUT_SECONDS = 60
OUTPUT_TAIL_CHARS = 2000
COMMAND_ECHO_CHARS = 300
SETUP_REFERENCE = "setup/AGENT_SETUP_PROTOCOL.md §2 P5"
ENVIRONMENT_NOTE = (
    "  這是環境錯誤，不是 verification failure；gate 仍然 block。\n"
    f"  修復：{SETUP_REFERENCE}。"
)


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


def capture(command, timeout, cwd):
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )


def output_tail(completed):
    # block reason 會進入 agent context，輸出必須有上限。
    text = (completed.stdout or "").strip()
    if not text:
        return "<no output>"
    if len(text) <= OUTPUT_TAIL_CHARS:
        return text
    return "…（前段省略）\n" + text[-OUTPUT_TAIL_CHARS:]


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
        },
        {
            "label": "ruff",
            "probe": [sys.executable, "-I", "-m", "ruff", "--version"],
            "command": [sys.executable, "-I", "-m", "ruff", "check", "."],
        },
    ]


def evaluate(check, index, cwd):
    """回傳 block reason；None 代表該 check 通過。"""
    header = f"[GATE:GREEN] configured command #{index} ({check['label']})"

    try:
        probe = capture(check["probe"], PROBE_TIMEOUT_SECONDS, cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (
            f"{header} ENVIRONMENT_NOT_READY：readiness probe 無法執行"
            f"（{type(exc).__name__}）。\n{ENVIRONMENT_NOTE}"
        )
    if probe.returncode != 0:
        return (
            f"{header} ENVIRONMENT_NOT_READY：readiness probe exit="
            f"{probe.returncode}。\n{ENVIRONMENT_NOTE}\n"
            f"  probe output:\n{output_tail(probe)}"
        )

    try:
        result = capture(check["command"], COMMAND_TIMEOUT_SECONDS, cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (
            f"{header} VERIFICATION_ERROR：命令無法完成（{type(exc).__name__}）。\n"
            f"  timeout={COMMAND_TIMEOUT_SECONDS}s"
        )
    if result.returncode != 0:
        return (
            f"{header} VERIFICATION_FAILED：exit={result.returncode}。\n"
            f"  command: {command_echo(check['command'])}\n"
            f"  output:\n{output_tail(result)}"
        )
    return None


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
