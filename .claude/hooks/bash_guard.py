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
# cd 的成敗不必用假設分支去猜：目錄存不存在是可以直接觀測的事實。
# 只有當同一行內可能先建立目錄時，才需要同時保留成功與失敗兩條分支，
# 那時候候選才會累積，因此仍保留上限。
CWD_CANDIDATE_LIMIT = 8
DIRECTORY_CREATING_COMMANDS = re.compile(
    r"\b(?:mkdir|install|git|tar|unzip|cp|mv|rsync)\b"
)
# 這些字元出現在 cd 的引數裡就無法靜態判定目的地。
OPAQUE_CD_ARGUMENT = ("$", "`", "~", "*", "?")
# bash 的 cd 只接受一個 [dir]（本機 help cd：cd [-L|[-P [-e]] [-@]] [dir]）；
# 多給一個 operand 是 "too many arguments"，工作目錄不會改變。


def split_tokens(segment):
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


# grep/rg/ag 的第一個 positional 是 PATTERN，sed 是 script，awk 是程式碼——都不是路徑。
# 把它們當路徑會誤擋 `rg checks app` 這種合法搜尋。
PATTERN_FIRST_READERS = frozenset({"grep", "rg", "ag", "sed", "awk"})
# 不給路徑時遞迴搜尋 cwd 的 reader；「沒有 operand」對它們本身就是一個 scope。
# grep 例外：GNU grep 只有在 recursive 時才讀 "."，否則讀 stdin，
# 把 `printf X | grep X` 當成 repo 全域搜尋是誤擋。
IMPLICIT_CWD_READERS = frozenset({"rg", "ag"})
RECURSIVE_GREP_OPTIONS = frozenset({"-r", "-R", "--recursive", "--dereference-recursive"})
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
# 這些選項不提供搜尋 pattern，但命令仍會開啟並讀取該檔案，其內容也會
# 改變可觀察的搜尋結果，因此一律計入 read target。
# 依本機 rg 14.1.0 --help：`--ignore-file=PATH` 載入 gitignore 格式的規則。
FILE_LONG_OPTIONS = frozenset(
    {"--file", "--exclude-from", "--include-from", "--ignore-file"}
)
VALUE_LONG_OPTIONS = PATTERN_LONG_OPTIONS | FILE_LONG_OPTIONS | frozenset(
    {"--max-count", "--include", "--exclude", "--glob", "--type"}
)
# rg 的這些模式沒有 pattern operand，第一個 positional 就是路徑。
NO_PATTERN_LONG_OPTIONS = frozenset({"--files", "--type-list", "--help", "--version"})
# 這幾個只印出資訊、完全不碰檔案系統，因此連 implicit cwd scope 都不該套用。
# --files 不在此列——它仍會列舉 cwd 底下的檔案。
NO_SEARCH_LONG_OPTIONS = frozenset({"--type-list", "--help", "--version"})
# 短旗標的語意逐命令不同（grep -h 是 --no-filename），只為已驗證的命令宣告。
# 依本機 rg 14.1.0 --help：`-h, --help`、`-V, --version`。
NO_SEARCH_SHORT_OPTIONS = {"rg": "hV"}
# 分組語法與 command prefix 必須先剝掉，否則 (cat x 的命令名會是 "(cat"。
# prefix 自己的選項也要吃掉，否則 command -p cat x 的命令名會變成 "-p"。
COMMAND_PREFIXES = {
    "command": "",
    "builtin": "",
    "exec": "",
    "env": "u",
    "time": "",
    "nohup": "",
    "nice": "n",
    "sudo": "u",
    # shell 控制關鍵字後面接的是要執行的命令列表。
    "if": "",
    "elif": "",
    "while": "",
    "until": "",
    "then": "",
    "do": "",
    "else": "",
}
GROUPING_CHARACTERS = "({!"
# 輸入重導向：<file、0<file、<>file（讀寫）。
# << 是 heredoc（其後是分隔字串不是路徑），<& 是 fd 複製，兩者排除。
INPUT_REDIRECTION = re.compile(r"^(\d*)<>?(?![<&])(.*)$")
# <<WORD 是 heredoc、<<<WORD 是 here-string；兩者的 operand 都是字串不是路徑，
# 當成 operand 會讓 grep SECRET <<< 'checks' 被誤判成搜尋測試側。
HERE_DOCUMENT = re.compile(r"^\d*<<<?(.*)$")
# 輸出重導向：>file、>>file、2>file。>& 是 fd 複製不是路徑。
OUTPUT_REDIRECTION = re.compile(r"^\d*>>?(?![&])(.*)$")
QUOTE_CHARACTERS = "\"'"
# [[ ]] 裡的 < 是字串比較，(( )) 裡的是數值比較，都不是重導向。
# 本機 bash 驗證：[[ app < checks/secret ]] 不讀取任何檔案；
# [ app < checks/secret ] 則確實重導向，所以只有雙括號形式在此豁免。
CONDITIONAL_OPENERS = ("[[", "((")
CONDITIONAL_CLOSERS = ("]]", "))")
# shell word 的結束字元；重導向目標讀到這些字元就停。
WORD_TERMINATORS = frozenset(" \t\n\r|;&<>()")


def _prefix_consumes_next(token, prefix_options):
    """prefix 的這個選項是否把下一個 token 當成值吃掉。

    -uPATH／-n10 的值已經黏在同一個 token 上，下一個 token 是要執行的命令；
    再吃掉它會讓 env -uPATH cat x 的命令名變成 x，整個 reader 判定失效。
    """
    if not prefix_options:
        return False
    if token.startswith("--"):
        return "=" not in token and any(
            letter in prefix_options for letter in token[2:]
        )
    letters = token[1:]
    for position, letter in enumerate(letters, start=1):
        if letter in prefix_options:
            # 吃值的字母必須是叢集的最後一個，值才會落在下一個 token。
            return position == len(letters)
    return False


def segment_command(tokens):
    """剝掉 env assignment、分組語法、重導向與 command prefix，回傳 (name, remaining)。"""
    index = 0
    prefix_options = ""
    while index < len(tokens):
        raw = tokens[index]
        token = raw.lstrip(GROUPING_CHARACTERS)
        if (
            not token
            or INPUT_REDIRECTION.match(token)
            or HERE_DOCUMENT.match(token)
            or OUTPUT_REDIRECTION.match(token)
        ):
            # 前置重導向不是命令名；其目標由 redirection_targets 另外抽取。
            index += 1
            continue
        if "=" in token and not token.startswith("-"):
            index += 1
            continue
        if token.startswith("-") and token != "-":
            # prefix 自己的選項；只有在值沒有黏在同一個 token 上時才吃下一個。
            if _prefix_consumes_next(token, prefix_options):
                index += 1
            index += 1
            continue
        name = PurePosixPath(token).name
        if name in COMMAND_PREFIXES:
            prefix_options = COMMAND_PREFIXES[name]
            index += 1
            continue
        return name, tokens[index + 1:]
    return None, []


def _quoted_segment(text, index):
    """回傳 (引號內的內容, 結束引號之後的位置)；引號未閉合時吃到文字結尾。"""
    quote = text[index]
    index += 1
    inner = []
    while index < len(text):
        character = text[index]
        if character == "\\" and quote == '"' and index + 1 < len(text):
            inner.append(text[index + 1])
            index += 2
            continue
        if character == quote:
            return "".join(inner), index + 1
        inner.append(character)
        index += 1
    return "".join(inner), index


def _read_word(text, index):
    """從 index 讀出一個 shell word（去掉引號），回傳 (word, next_index)。"""
    while index < len(text) and text[index] in " \t":
        index += 1
    word = []
    while index < len(text):
        character = text[index]
        if character == "\\" and index + 1 < len(text):
            word.append(text[index + 1])
            index += 2
            continue
        if character in QUOTE_CHARACTERS:
            inner, index = _quoted_segment(text, index)
            word.append(inner)
            continue
        if character in WORD_TERMINATORS:
            break
        word.append(character)
        index += 1
    return "".join(word), index


def redirection_targets(segment):
    """回傳 (讀取目標, 寫入目標)；重導向讓任何命令都變成 reader 或 writer。

    必須在原始文字上判定，不能用 shlex 的 token：shlex 已經把引號拿掉，
    printf '%s' '<checks/x' 這種純字串會與真正的重導向無法區分，
    當成重導向就是誤擋。
    """
    reads = []
    writes = []
    conditional = 0
    index = 0
    while index < len(segment):
        character = segment[index]
        if character == "\\":
            index += 2
            continue
        if character in QUOTE_CHARACTERS:
            _, index = _quoted_segment(segment, index)
            continue
        if any(segment.startswith(opener, index) for opener in CONDITIONAL_OPENERS):
            conditional += 1
            index += 2
            continue
        if conditional and any(
            segment.startswith(closer, index) for closer in CONDITIONAL_CLOSERS
        ):
            conditional -= 1
            index += 2
            continue
        if character not in "<>":
            index += 1
            continue
        if conditional:
            # 條件式／算術式裡的 < 與 > 是比較運算子。
            index += 1
            continue
        following = segment[index + 1:index + 2]
        if character == "<":
            if segment.startswith("<<<", index):
                # here-string 的 operand 是字串不是檔案。
                _, index = _read_word(segment, index + 3)
                continue
            if following in ("<", "&", "("):
                # heredoc 的 operand 是分隔字串，<& 是 fd 複製，
                # <( 由 segment 切割處理。
                index += 2
                continue
            index += 2 if following == ">" else 1  # <> 是讀寫
            target, index = _read_word(segment, index)
            if target:
                reads.append(target)
            continue
        if following in ("&", "("):
            index += 2
            continue
        index += 2 if following == ">" else 1  # >> 是追加
        target, index = _read_word(segment, index)
        if target:
            writes.append(target)
    return reads, writes


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


def _has_option(name, tokens, long_options, short_letters):
    """短選項叢集必須依 arity 掃描：吃值的字母之後全是它的值，不是選項。

    否則 rg -g'*.h' 的 h 會被當成 -h／--help，整個 scope 判定就被跳過。
    """
    value_letters = READER_OPTIONS.get(name, NO_VALUE_OPTIONS)["value"]
    for token in tokens:
        if token.split("=", 1)[0] in long_options:
            return True
        if not short_letters or not token.startswith("-") or token.startswith("--"):
            continue
        for letter in token[1:]:
            if letter in short_letters:
                return True
            if letter in value_letters:
                break
    return False


def no_pattern_mode(name, tokens):
    """這次呼叫是否沒有 pattern operand（第一個 positional 就是路徑）。"""
    return _has_option(
        name, tokens, NO_PATTERN_LONG_OPTIONS, NO_SEARCH_SHORT_OPTIONS.get(name, "")
    )


def no_search_mode(name, tokens):
    """這次呼叫是否只印出資訊、完全不讀檔案系統。"""
    return _has_option(
        name, tokens, NO_SEARCH_LONG_OPTIONS, NO_SEARCH_SHORT_OPTIONS.get(name, "")
    )


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
        here = HERE_DOCUMENT.match(token)
        if here:
            if not here.group(1) and index < len(tokens):
                index += 1  # 分隔字串／字串 operand 落在下一個 token
            continue
        output = OUTPUT_REDIRECTION.match(token)
        if output:
            # 輸出重導向的目標是寫入而不是讀取，由 redirection_targets 另外分類。
            if not output.group(1) and index < len(tokens):
                index += 1
            continue
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
    if (
        name in PATTERN_FIRST_READERS
        and not pattern_supplied
        and not no_pattern_mode(name, tokens)
        and operands
    ):
        operands = operands[1:]
    return operands + file_values


def implicit_cwd_scope(name, tokens):
    """不帶路徑 operand 時，這次呼叫是否會遞迴搜尋 cwd。"""
    if no_search_mode(name, tokens):
        # rg --help／--version／--type-list 只印出資訊，沒有 cwd scope 可言。
        return False
    if name in IMPLICIT_CWD_READERS:
        return True
    if name != "grep":
        return False
    return any(
        token in RECURSIVE_GREP_OPTIONS
        or (
            token.startswith("-")
            and not token.startswith("--")
            and any(letter in "rR" for letter in token[1:])
        )
        for token in tokens
    )


def cd_destination(tokens):
    """回傳 cd 的目的地。

    None 代表這個 cd 必定失敗、工作目錄不變（operand 超過一個）；
    "" 代表目的地無法靜態判定（無 operand、cd -、含變數或萬用字元）。
    """
    destinations = path_operands("cd", tokens)
    if len(destinations) > 1:
        return None
    if not destinations or destinations[0] == "-" or any(
        character in destinations[0] for character in OPAQUE_CD_ARGUMENT
    ):
        return ""
    return destinations[0]


def _resolve(argument, cwds):
    """相對路徑要對每個候選 cwd 各解析一次。"""
    if Path(argument).is_absolute():
        return [argument]
    return [os.path.normpath(str(candidate / argument)) for candidate in cwds]


def shell_targets(shell_command, root):
    """回傳 (讀取目標, 寫入目標)，並追蹤同一行內的 cd。

    cd 目的地無法靜態判定時，退回以 repository root 解析而不是擋下：這支 guard
    也會掃到 heredoc 與引號內的文字，把「判不出來」一律當成違規會讓整行後續的
    reader 全部誤判。shell 是開放式的，這是 best-effort，不是安全邊界。
    """
    targets = []
    written = []
    # cd 到不存在的目錄一定失敗，這是可以直接觀測的事實，不必用假設分支去猜。
    # 例外是同一行內可能先建立目錄，那時才保留成功與失敗兩條分支。
    may_create = DIRECTORY_CREATING_COMMANDS.search(shell_command) is not None
    # success_cwd 是「每個 cd 都成功」的路徑；分支展開時優先保留它。
    success_cwd = root
    cwds = [root]
    # 換行在 shell 裡也是 command separator；<( 與 >( 是 process substitution，
    # 其括號內是另一個完整命令，與 $( 一樣要當成獨立 segment。
    # 保留分隔符是為了知道 segment 是不是接在 pipe 之後——那代表它讀 stdin。
    parts = re.split(r"([|;&\n\r]+|[<>]\(|\$\(|\)|`)", shell_command)
    for position, segment in enumerate(parts[::2]):
        separator = parts[2 * position - 1] if position else ""
        piped = "|" in separator
        tokens = split_tokens(segment)
        # 重導向可能出現在命令名之前（<file cat），所以掃整個 segment。
        # 重導向讓任何命令都讀得到檔案，與命令是不是 reader 無關。
        arguments, redirected = redirection_targets(segment)
        name, remaining = segment_command(tokens)
        if name in CD_COMMANDS:
            destination = cd_destination(remaining)
            if destination is None:
                # arity 不合法，cd 必定失敗，工作目錄不變。
                pass
            elif not destination:
                success_cwd = root
                cwds = [root]
            else:
                success_cwd = success_cwd / destination
                candidates = [success_cwd, root] if may_create else []
                for candidate in cwds:
                    reached = candidate / destination
                    if reached.is_dir():
                        # 目錄存在，cd 必定成功；沒有失敗分支要保留。
                        candidates.append(reached)
                    elif may_create:
                        # 成功分支緊接在自己的失敗分支之前，截斷不會只留下其中一邊。
                        candidates.extend([reached, candidate])
                    else:
                        candidates.append(candidate)
                cwds = list(dict.fromkeys(candidates))[:CWD_CANDIDATE_LIMIT]
        elif name in READ_COMMANDS:
            arguments += path_operands(name, remaining)
        if not arguments and not piped and implicit_cwd_scope(name, remaining):
            # 這些 reader 不帶路徑時遞迴搜尋 cwd，那就是這次搜尋的 scope。
            arguments = ["."]
        for argument in arguments:
            targets.extend(_resolve(argument, cwds))
        for argument in redirected:
            written.extend(_resolve(argument, cwds))
    return targets, written


# 被隔離的那一側不存在時（例如本 governance repository 沒有 src/），
# 沒有東西可讀，整段 read 判定跳過。
forbidden = forbidden_side(phase)
if forbidden is not None and isolated_side_exists(policy, forbidden, root):
    side_label = "測試" if forbidden == "test" else "實作"
    reads, writes = shell_targets(command, root)
    for target in reads:
        if classify_path(target, policy) == forbidden:
            read_violations.append(f"讀取 {target}（{side_label}側）")
        elif scope_reaches_forbidden(target, policy, forbidden):
            # 目錄 operand 會被遞迴搜尋，`rg SECRET .` 一樣讀得到隔離側。
            read_violations.append(f"搜尋範圍 {target} 涵蓋{side_label}側")
    for target in writes:
        # 重導向到被隔離的一側是寫入，不是讀取；標成「讀取」會誤導 agent
        # 去找根本不存在的讀取行為。governed_roots 的 pattern 不涵蓋 test_roots，
        # 這裡是它唯一會被攔下的地方。
        if classify_path(target, policy) == forbidden:
            read_violations.append(f"重導向寫入 {target}（{side_label}側）")

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
