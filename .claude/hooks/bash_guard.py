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
# 選項 arity 必須逐命令定義：cat -e／-t 是顯示旗標，套用 grep 的 arity 會把
# 檔案 operand 當成選項值吃掉。少宣告只會多出幾個 other 分類的 operand（無害），
# 多宣告會吃掉真正的路徑（有害），因此只為確實吃值的 reader 宣告。
READER_OPTIONS = {
    "grep": {"value": "efm", "pattern": "ef", "file": "f"},
    "rg": {"value": "efmgt", "pattern": "ef", "file": "f"},
    "ag": {"value": "efm", "pattern": "ef", "file": "f"},
    "sed": {"value": "ef", "pattern": "ef", "file": "f"},
    "awk": {"value": "fv", "pattern": "f", "file": "f"},
}
NO_VALUE_OPTIONS = {"value": "", "pattern": "", "file": ""}
PATTERN_LONG_OPTIONS = frozenset({"--regexp", "--file", "--expression"})
FILE_LONG_OPTIONS = frozenset({"--file"})
VALUE_LONG_OPTIONS = PATTERN_LONG_OPTIONS | frozenset(
    {"--max-count", "--include", "--exclude", "--glob", "--type"}
)
# 分組語法與 command prefix 必須先剝掉，否則 (cat x 的命令名會是 "(cat"。
COMMAND_PREFIXES = frozenset(
    {"command", "builtin", "exec", "env", "time", "nohup", "nice", "sudo", "then", "do", "else"}
)
GROUPING_CHARACTERS = "({!"
# 附著式輸入重導向：<file、0<file。<< 是 heredoc，其後是分隔字串不是路徑。
INPUT_REDIRECTION = re.compile(r"^(\d*)<(?![<&])(.*)$")


def segment_command(tokens):
    """剝掉 env assignment、分組語法與 command prefix，回傳 (name, remaining)。"""
    index = 0
    while index < len(tokens):
        token = tokens[index].lstrip(GROUPING_CHARACTERS)
        if not token:
            index += 1
            continue
        if "=" in token and not token.startswith("-"):
            index += 1
            continue
        name = PurePosixPath(token).name
        if name in COMMAND_PREFIXES:
            index += 1
            continue
        return name, tokens[index + 1:]
    return None, []


def redirection_targets(tokens):
    """取出附著式輸入重導向的檔案；重導向讓任何命令都變成 reader。"""
    targets = []
    index = 0
    while index < len(tokens):
        match = INPUT_REDIRECTION.match(tokens[index])
        index += 1
        if match is None:
            continue
        attached = match.group(2)
        if attached:
            targets.append(attached)
        elif index < len(tokens):
            targets.append(tokens[index])
            index += 1
    return targets


def _long_option(token, tokens, index):
    """回傳 (pattern_supplied, file_value, next_index)。"""
    option, _, attached = token.partition("=")
    supplied = option in PATTERN_LONG_OPTIONS
    value = attached or None
    if value is None and option in VALUE_LONG_OPTIONS and index < len(tokens):
        value = tokens[index]
        index += 1
    return supplied, value if option in FILE_LONG_OPTIONS else None, index


def _short_options(token, tokens, index, options):
    """處理短選項叢集；值可能黏在同一個 token 上（-ePATTERN）或落在下一個 token。"""
    supplied = False
    file_value = None
    letters = token[1:]
    position = 0
    while position < len(letters):
        letter = letters[position]
        position += 1
        if letter not in options["value"]:
            continue
        supplied = supplied or letter in options["pattern"]
        attached = letters[position:]
        if attached:
            value = attached
        elif index < len(tokens):
            value = tokens[index]
            index += 1
        else:
            value = None
        if letter in options["file"]:
            file_value = value
        break
    return supplied, file_value, index


def path_operands(name, tokens):
    """從 reader 的引數取出真正的路徑 operand。

    -f／--file 的值本身就是要被讀取的 pattern 檔，因此同時計入 read target。
    """
    options = READER_OPTIONS.get(name, NO_VALUE_OPTIONS)
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
        if INPUT_REDIRECTION.match(token):
            continue  # 重導向由 redirection_targets 單獨處理
        if not token.startswith("-") or token == "-":
            if token:
                operands.append(token)
            continue
        if token.startswith("--"):
            supplied, file_value, index = _long_option(token, tokens, index)
        else:
            supplied, file_value, index = _short_options(token, tokens, index, options)
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
        # 輸入重導向讓任何命令都讀得到檔案，與命令是不是 reader 無關。
        arguments = redirection_targets(tokens)
        if name in CD_COMMANDS:
            destinations = path_operands(name, tokens)
            opaque = not destinations or destinations[0] == "-" or any(
                character in destinations[0] for character in OPAQUE_CD_ARGUMENT
            )
            cwd = root if opaque else cwd / destinations[0]
        elif name in READ_COMMANDS:
            arguments += path_operands(name, tokens)
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
