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
    scope_reaches_forbidden,
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


# grep/rg/ag 的第一個 positional 是 PATTERN，sed 是 script，awk 是程式碼——都不是路徑。
# 把它們當路徑會誤擋 `rg checks app` 這種合法搜尋。
PATTERN_FIRST_READERS = frozenset({"grep", "rg", "ag", "sed", "awk"})
# 不給路徑時遞迴搜尋 cwd，因此「沒有 operand」本身就是一個 scope。
SEARCH_READERS = frozenset({"grep", "rg", "ag"})
# 短選項可以黏著值（-ePATTERN、-fFILE），也可以吃下一個 token。
VALUE_SHORT_OPTIONS = "efmgt"
PATTERN_SHORT_OPTIONS = "ef"
FILE_SHORT_OPTIONS = "f"
PATTERN_LONG_OPTIONS = frozenset({"--regexp", "--file", "--expression"})
FILE_LONG_OPTIONS = frozenset({"--file"})
VALUE_LONG_OPTIONS = PATTERN_LONG_OPTIONS | frozenset(
    {"--max-count", "--include", "--exclude", "--glob", "--type"}
)


def segment_command(tokens):
    """跳過前置 env assignment，回傳 (command_name, remaining_tokens)。"""
    index = 0
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-"):
        index += 1
    if index >= len(tokens):
        return None, []
    return PurePosixPath(tokens[index]).name, tokens[index + 1:]


def _long_option(token, tokens, index):
    """回傳 (pattern_supplied, file_value, next_index)。"""
    option, _, attached = token.partition("=")
    supplied = option in PATTERN_LONG_OPTIONS
    value = attached or None
    if value is None and option in VALUE_LONG_OPTIONS and index < len(tokens):
        value = tokens[index]
        index += 1
    return supplied, value if option in FILE_LONG_OPTIONS else None, index


def _short_options(token, tokens, index):
    """處理短選項叢集；值可能黏在同一個 token 上（-ePATTERN）或落在下一個 token。"""
    supplied = False
    file_value = None
    letters = token[1:]
    position = 0
    while position < len(letters):
        letter = letters[position]
        position += 1
        if letter not in VALUE_SHORT_OPTIONS:
            continue
        supplied = supplied or letter in PATTERN_SHORT_OPTIONS
        attached = letters[position:]
        if attached:
            value = attached
        elif index < len(tokens):
            value = tokens[index]
            index += 1
        else:
            value = None
        if letter in FILE_SHORT_OPTIONS:
            file_value = value
        break
    return supplied, file_value, index


def path_operands(name, tokens):
    """從 reader 的引數取出真正的路徑 operand。

    -f／--file 的值本身就是要被讀取的 pattern 檔，因此同時計入 read target。
    """
    operands = []
    file_values = []
    pattern_supplied = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token == "--":
            operands.extend(item for item in tokens[index:] if item)
            break
        if not token.startswith("-") or token == "-":
            if token:
                operands.append(token)
            continue
        handler = _long_option if token.startswith("--") else _short_options
        supplied, file_value, index = handler(token, tokens, index)
        pattern_supplied = pattern_supplied or supplied
        if file_value:
            file_values.append(file_value)
    if name in PATTERN_FIRST_READERS and not pattern_supplied and operands:
        operands = operands[1:]
    return operands + file_values


def read_targets(shell_command, root):
    """回傳 reader command 的引數，並追蹤同一行內的 cd。

    cd 目的地無法靜態判定時，退回以 repository root 解析而不是擋下：這支 guard
    也會掃到 heredoc 與引號內的文字，把「判不出來」一律當成違規會讓整行後續的
    reader 全部誤判。shell 是開放式的，這是 best-effort，不是安全邊界。
    """
    targets = []
    cwd = root
    # 換行在 shell 裡也是 command separator，漏掉它就會讓整段多行命令只被當成一個 segment。
    for segment in re.split(r"[|;&\n\r]+|\$\(|\)|`", shell_command):
        name, tokens = segment_command(split_tokens(segment))
        if name is None:
            continue
        if name in CD_COMMANDS:
            arguments = path_operands(name, tokens)
            opaque = not arguments or arguments[0] == "-" or any(
                character in arguments[0] for character in OPAQUE_CD_ARGUMENT
            )
            cwd = root if opaque else cwd / arguments[0]
            continue
        if name not in READ_COMMANDS:
            continue
        arguments = path_operands(name, tokens)
        if not arguments and name in SEARCH_READERS:
            # rg／grep 不帶路徑時遞迴搜尋 cwd，那就是這次搜尋的 scope。
            arguments = ["."]
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
        elif scope_reaches_forbidden(target, policy, forbidden):
            # 目錄 operand 會被遞迴搜尋，`rg SECRET .` 一樣讀得到隔離側。
            read_violations.append(f"搜尋範圍 {target} 涵蓋{side_label}側")

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
