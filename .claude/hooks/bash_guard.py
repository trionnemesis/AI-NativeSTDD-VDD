#!/usr/bin/env python3
# Why: prevent common Bash writes from bypassing configured SPEC/RED paths,
# and common Bash reads from bypassing the read-side isolation guard.
# Shell 是開放式的，pattern 比對只擋得住常見寫法；真正的隔離仍靠 role separation。
import json
import os
import re
import shlex
import sys
from pathlib import Path, PurePosixPath

from path_policy import (
    PolicyError,
    classify_path,
    forbidden_side,
    isolated_side_exists,
    load_policy,
    project_root,
    read_phase,
)

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

try:
    policy = load_policy()
    root = project_root()
    phase = read_phase(root)
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)

patterns = []
read_violations = []
governed_roots = dict.fromkeys(
    [*policy["implementation_roots"], *policy["protected_spec_roots"]]
)
for governed_root in governed_roots:
    relative = re.escape(governed_root)
    absolute = re.escape((root / governed_root).as_posix())
    target = rf"[\"']?(?:(?:\./)?{relative}|{absolute})/"
    patterns.extend(
        [
            (rf">\s*{target}", f"重導向寫入 {governed_root}/"),
            (rf"\btee\s+{target}", f"tee 寫入 {governed_root}/"),
            (rf"\bsed\s+-i.*{target}", f"sed -i 修改 {governed_root}/"),
            (rf"\bcat\s+>.*{target}", f"cat 寫入 {governed_root}/"),
            (rf"\becho\s+.*>\s*{target}", f"echo 寫入 {governed_root}/"),
            (rf"\bcp\s+.*\s+{target}", f"cp 到 {governed_root}/"),
            (rf"\bmv\s+.*\s+{target}", f"mv 到 {governed_root}/"),
        ]
    )

# read-side isolation：與 read_isolation_guard.py 共用同一組 lane 與 path 分類，
# 兩側若各自實作就會漂移出不同語意。regex 只用來切出 reader command 的引數，
# 真正的判定交給 classify_path，這樣 co-located test（app/login.spec.ts）與
# 不帶斜線的 root（rg assert tests）都擋得住。
READ_COMMANDS = frozenset(
    {
        "cat", "head", "tail", "less", "more", "bat", "nl", "od", "xxd",
        "strings", "grep", "rg", "ag", "awk", "sed",
    }
)
CD_COMMANDS = frozenset({"cd", "pushd", "chdir"})
# 這些字元出現在 cd 的引數裡就無法靜態判定目的地。
OPAQUE_CD_ARGUMENT = ("$", "`", "~", "*", "?")


def split_tokens(segment):
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def segment_command(tokens):
    """跳過前置 env assignment，回傳 (command_name, positional_arguments)。"""
    index = 0
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-"):
        index += 1
    if index >= len(tokens):
        return None, []
    arguments = [
        token for token in tokens[index + 1:] if token and not token.startswith("-")
    ]
    return PurePosixPath(tokens[index]).name, arguments


def read_targets(shell_command, root):
    """回傳 reader command 的引數，並追蹤同一行內的 cd。

    cd 目的地無法靜態判定時，退回以 repository root 解析而不是擋下：這支 guard
    也會掃到 heredoc 與引號內的文字，把「判不出來」一律當成違規會讓整行後續的
    reader 全部誤判。shell 是開放式的，這是 best-effort，不是安全邊界。
    """
    targets = []
    cwd = root
    for segment in re.split(r"[|;&]+|\$\(|\)|`", shell_command):
        name, arguments = segment_command(split_tokens(segment))
        if name is None:
            continue
        if name in CD_COMMANDS:
            opaque = not arguments or arguments[0] == "-" or any(
                character in arguments[0] for character in OPAQUE_CD_ARGUMENT
            )
            cwd = root if opaque else cwd / arguments[0]
            continue
        if name not in READ_COMMANDS:
            continue
        for argument in arguments:
            if Path(argument).is_absolute():
                targets.append(argument)
            else:
                targets.append(os.path.normpath(str(cwd / argument)))
    return targets


# 被隔離的那一側不存在時（例如本 governance repository 沒有 src/），
# 沒有東西可讀，整段 read 判定跳過。
forbidden = forbidden_side(phase)
if forbidden is not None and isolated_side_exists(policy, forbidden, root):
    side_label = "測試" if forbidden == "test" else "實作"
    for target in read_targets(command, root):
        if classify_path(target, policy) == forbidden:
            read_violations.append(f"讀取 {target}（{side_label}側）")

violations = [label for pattern, label in patterns if re.search(pattern, command)]
violations.extend(read_violations)
if violations:
    print(
        "BLOCKED [GATE:SPEC/RED/BASH]: 偵測到透過 Bash 繞過 gate 的嘗試。\n"
        f"  Violations: {', '.join(violations)}\n"
        f"  phase: {phase!r}\n"
        "  寫入請改用 Edit／Write tool，讓 configured hook 正確觸發；\n"
        "  讀取對側受 GATE:RED agent_isolation_enforced 限制，不得以 Bash 繞過。",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
