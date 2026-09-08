#!/usr/bin/env python3
# Why: prevent common Bash writes from bypassing configured SPEC/RED paths,
# and common Bash reads from bypassing the read-side isolation guard.
# Shell 是開放式的，pattern 比對只擋得住常見寫法；真正的隔離仍靠 role separation。
import json
import os
import re
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


class Word(str):
    """cooked 之後的 token，額外帶著引號遮罩。

    mask 與字串等長，"q" 代表該字元來自引號或跳脫。brace expansion 必須
    看得到這個資訊：bash 只展開沒被引號包住的大括號，而任何先 cook 再判斷的
    做法都已經把它丟掉了。這是本 guard 第三次因為引號資訊在錯誤的階段消失
    而出錯，所以改為讓 token 自己帶著。
    """

    __slots__ = ("mask",)

    def __new__(cls, text, mask):
        word = super().__new__(cls, text)
        word.mask = mask
        return word


def word_mask(token):
    """取出 token 的引號遮罩；沒有遮罩的字串一律視為未引號。"""
    return getattr(token, "mask", None) or "." * len(token)


def slice_word(token, start):
    """切出 token[start:] 並保留對應的遮罩片段。

    附著式選項值（--exclude-from="{a,b}/x"、-f"{a,b}/x"）如果丟掉遮罩，
    引號內的大括號就會被誤展開——遮罩必須跟著切。
    """
    return Word(str(token)[start:], word_mask(token)[start:])


def split_tokens(segment):
    """把 segment 切成 Word；引號與跳脫在此 cook，遮罩同時建立。"""
    words = []
    index = 0
    length = len(segment)
    while index < length:
        while index < length and segment[index] in " \t\n\r":
            index += 1
        if index >= length:
            break
        text = []
        mask = []
        while index < length and segment[index] not in " \t\n\r":
            character = segment[index]
            if character == "\\" and index + 1 < length:
                text.append(segment[index + 1])
                mask.append("q")
                index += 2
                continue
            if character in QUOTE_CHARACTERS:
                inner, index = _quoted_segment(segment, index)
                text.append(inner)
                mask.append("q" * len(inner))
                continue
            text.append(character)
            mask.append(".")
            index += 1
        words.append(Word("".join(text), "".join(mask)))
    return words


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
    "env": "uC",
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
# GNU env 的 -C DIR／--chdir=DIR 會在執行命令前切換工作目錄
# （本機 env --help：`-C, --chdir=DIR  change working directory to DIR`），
# 只把它當成一般吃值的選項會漏掉 env -C app cat ../checks/secret。
PREFIX_CHDIR_OPTIONS = {"env": ("C", "--chdir")}
# bash 的 cd 只接受這些選項（本機 help cd：cd [-L|[-P [-e]] [-@]] [dir]）；
# 其餘一律是 invalid option，cd 必定失敗。
CD_OPTIONS = "LPe@"
# brace expansion 展開上限。上限之內逐條精確判定；超過就整個 word 退回
# repository scope。先前用「大括號之前的字面前綴」當保守 scope，兩輪之內
# 產生了三則 finding（前綴切在路徑元件中間、range 語法自己的 .. 被誤判、
# 後綴的 .. 跳出前綴）——那個啟發式的缺陷率高於它換來的精度，因此移除。
# 上限拉高到 1024，讓實務上寫得出來的 brace 都落在精確列舉的範圍內。
BRACE_EXPANSION_LIMIT = 1024
BRACE_RANGE = re.compile(
    r"^(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?$"
    r"|^([A-Za-z])\.\.([A-Za-z])(?:\.\.(-?\d+))?$"
)
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
# 雙引號內只有這些字元前面的反斜線會被 shell 吃掉；其餘保留字面。
# 本機 bash 5.2.21 驗證：printf "%s" "check\\s/x" 印出 check\\s/x。
DOUBLE_QUOTE_ESCAPES = "$`\"\\\n"
# [[ ]] 裡的 < 是字串比較，(( )) 裡的是數值比較，都不是重導向。
# 本機 bash 驗證：[[ app < checks/secret ]] 不讀取任何檔案；
# [ app < checks/secret ] 則確實重導向，所以只有雙括號形式在此豁免。
CONDITIONAL_OPENERS = ("[[", "((")
CONDITIONAL_CLOSERS = ("]]", "))")
# 只有出現在命令位置的 [[ ／(( 才會開啟條件式；echo [[ 的 [[ 只是引數。
CONTROL_KEYWORDS = ("if", "elif", "while", "until", "then", "do", "else")
# shell word 的結束字元；重導向目標讀到這些字元就停。
WORD_TERMINATORS = frozenset(" \t\n\r|;&<>()")


def _prefix_option(token, tokens, index, prefix_options, chdir_option):
    """解析 prefix 自己的選項，回傳 (chdir 目的地或 None, 是否吃掉下一個 token)。

    -uPATH／-n10 的值已經黏在同一個 token 上，下一個 token 是要執行的命令；
    再吃掉它會讓 env -uPATH cat x 的命令名變成 x，整個 reader 判定失效。
    """
    if not prefix_options:
        return None, False
    if token.startswith("--"):
        option, separator, attached = token.partition("=")
        if chdir_option and option == chdir_option[1]:
            if separator:
                return attached, False
            return (tokens[index] if index < len(tokens) else None), True
        return None, not separator and any(
            letter in prefix_options for letter in token[2:]
        )
    letters = token[1:]
    for position, letter in enumerate(letters, start=1):
        if letter not in prefix_options:
            continue
        # 吃值的字母之後全是它的值；值黏著時下一個 token 就是命令本身。
        attached = letters[position:]
        wanted = bool(chdir_option) and letter == chdir_option[0]
        if attached:
            return (attached if wanted else None), False
        value = tokens[index] if index < len(tokens) else None
        return (value if wanted else None), True
    return None, False


def segment_command(tokens):
    """剝掉 env assignment、分組語法、重導向與 command prefix。

    回傳 (name, remaining, chdir)；chdir 是 prefix 自己造成的工作目錄變更。
    """
    index = 0
    prefix_options = ""
    chdir_option = None
    chdir = None
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
            destination, consumes = _prefix_option(
                token, tokens, index + 1, prefix_options, chdir_option
            )
            if destination:
                chdir = destination
            index += 2 if consumes else 1
            continue
        name = PurePosixPath(token).name
        if name in COMMAND_PREFIXES:
            prefix_options = COMMAND_PREFIXES[name]
            chdir_option = PREFIX_CHDIR_OPTIONS.get(name)
            index += 1
            continue
        return name, tokens[index + 1:], chdir
    return None, [], chdir


def _quoted_segment(text, index):
    """回傳 (引號內的內容, 結束引號之後的位置)；引號未閉合時吃到文字結尾。"""
    quote = text[index]
    index += 1
    inner = []
    while index < len(text):
        character = text[index]
        if (
            character == "\\"
            and quote == '"'
            and index + 1 < len(text)
            and text[index + 1] in DOUBLE_QUOTE_ESCAPES
        ):
            inner.append(text[index + 1])
            index += 2
            continue
        if character == quote:
            return "".join(inner), index + 1
        inner.append(character)
        index += 1
    return "".join(inner), index


def _read_word(text, index):
    """從 index 讀出一個 shell word（去掉引號），回傳 (Word, next_index)。

    重導向目標與 operand 走同一套引號遮罩，`cat < '{a,b}'` 才不會被誤展開。
    """
    while index < len(text) and text[index] in " \t":
        index += 1
    word = []
    mask = []
    while index < len(text):
        character = text[index]
        if character == "\\" and index + 1 < len(text):
            word.append(text[index + 1])
            mask.append("q")
            index += 2
            continue
        if character in QUOTE_CHARACTERS:
            inner, index = _quoted_segment(text, index)
            word.append(inner)
            mask.append("q" * len(inner))
            continue
        if character in WORD_TERMINATORS:
            break
        word.append(character)
        mask.append(".")
        index += 1
    return Word("".join(word), "".join(mask)), index


def command_position(segment):
    """回傳 segment 中命令字的起始位置（跳過空白、! 與控制關鍵字）。"""
    index = 0
    while index < len(segment):
        if segment[index] in " \t!":
            index += 1
            continue
        if segment[index] == "(" and not segment.startswith("((", index):
            # 單一 ( 是 subshell；(( 本身就是算術式的開頭，不能跳過。
            index += 1
            continue
        for keyword in CONTROL_KEYWORDS:
            end = index + len(keyword)
            if segment.startswith(keyword, index) and (
                end >= len(segment) or segment[end] in " \t"
            ):
                index = end
                break
        else:
            break
    return index


def redirection_targets(segment, conditional=0):
    """回傳 (讀取目標, 寫入目標, 結束時的條件式深度)。

    必須在原始文字上判定，不能用 shlex 的 token：shlex 已經把引號拿掉，
    printf '%s' '<checks/x' 這種純字串會與真正的重導向無法區分，
    當成重導向就是誤擋。
    """
    reads = []
    writes = []
    opener_position = command_position(segment)
    index = 0
    while index < len(segment):
        character = segment[index]
        if character == "\\":
            index += 2
            continue
        if character in QUOTE_CHARACTERS:
            _, index = _quoted_segment(segment, index)
            continue
        if (conditional or index == opener_position) and any(
            segment.startswith(opener, index) for opener in CONDITIONAL_OPENERS
        ):
            # 已在條件式內就允許巢狀（[[:alpha:]] 之類），否則只認命令位置。
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
    return reads, writes, conditional


def _long_option(token, tokens, index):
    """回傳 (pattern_supplied, file_value, next_index)。"""
    option, separator, attached = str(token).partition("=")
    supplied = option in PATTERN_LONG_OPTIONS
    value = slice_word(token, len(option) + 1) if separator and attached else None
    if value is None and option in VALUE_LONG_OPTIONS and index < len(tokens):
        value = tokens[index]
        index += 1
    return supplied, value if option in FILE_LONG_OPTIONS else None, index


def _short_options(token, tokens, index, options):
    """處理短選項叢集；值可能黏在同一個 token 上（-ePATTERN）或落在下一個 token。"""
    supplied = False
    file_value = None
    letters = str(token)[1:]
    position = 0
    while position < len(letters):
        letter = letters[position]
        position += 1
        if letter not in options["value"]:
            continue
        supplied = supplied or letter in options["pattern"]
        attached = letters[position:]
        if attached:
            value = slice_word(token, position + 1)
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
    for token in tokens:
        if token == "--":
            break
        if token.startswith("-") and token != "-" and any(
            letter not in CD_OPTIONS for letter in token[1:]
        ):
            # invalid option，bash 直接拒絕，工作目錄不變。
            return None
    destinations = path_operands("cd", tokens)
    if len(destinations) > 1:
        return None
    if not destinations or destinations[0] == "-" or any(
        character in destinations[0] for character in OPAQUE_CD_ARGUMENT
    ):
        return ""
    return destinations[0]


def _unquoted_brace(text, mask):
    """第一個未被引號包住的左大括號位置；沒有就回傳 -1。"""
    for index, character in enumerate(text):
        if character == "{" and mask[index] == ".":
            return index
    return -1


def _brace_close(text, mask, start):
    """與 start 配對的右大括號位置；沒有配對就回傳 -1。"""
    depth = 0
    for index in range(start, len(text)):
        if mask[index] != ".":
            continue
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _brace_alternatives(text, mask, start, end):
    """依最外層未被引號包住的逗號切開，回傳 [(text, mask)]。"""
    parts = []
    depth = 0
    piece = start + 1
    for index in range(start + 1, end):
        if mask[index] != ".":
            continue
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append((text[piece:index], mask[piece:index]))
            piece = index + 1
    parts.append((text[piece:end], mask[piece:end]))
    return parts


def _padded(value, width):
    """依 bash 的零填充規則格式化 range 值。"""
    if not width:
        return str(value)
    sign = "-" if value < 0 else ""
    return sign + str(abs(value)).rjust(width - len(sign), "0")


def _brace_range(body):
    """{1..3}／{a..c}／{1..9..2} 的展開值；不是 range 就回傳 None。"""
    match = BRACE_RANGE.match(body)
    if match is None:
        return None
    if match.group(1) is not None:
        first, last = match.group(1), match.group(2)
        start, end = int(first), int(last)
        step = abs(int(match.group(3))) if match.group(3) else 1
        direction = 1 if end >= start else -1
        # 端點有前導零時 bash 會把結果補到相同寬度：{01..03} → 01 02 03。
        # 轉成 int 再轉回字串會把填充洗掉，checks{01..03} 就變成 checks1。
        padded = any(
            item.lstrip("-").startswith("0") and len(item.lstrip("-")) > 1
            for item in (first, last)
        )
        width = max(len(first), len(last)) if padded else 0
        values = range(start, end + direction, direction * (step or 1))
        return [_padded(value, width) for value in values]
    # 字母 range 同樣接受 step：bash 的 {q..u..2} 展開為 q s u。
    start, end = ord(match.group(4)), ord(match.group(5))
    step = abs(int(match.group(6))) if match.group(6) else 1
    direction = 1 if end >= start else -1
    values = range(start, end + direction, direction * (step or 1))
    return [chr(value) for value in values]


def expand_braces(text, mask):
    """展開靜態可判定的 brace expression，回傳 (展開結果, 是否被上限截斷)。

    bash 的 cat {app,checks}/secret 會讀取兩個檔案，只看字面字串會分類成 other。
    只展開遮罩標為未引號的大括號——bash 不展開 '{a,b}'，但對
    {a,"b"} 這種只有內容被引的仍然展開，所以粒度必須是「大括號字元本身」。
    沒有配對括號、既不是 alternation 也不是 range 時原樣保留，與 bash 一致。
    超過上限時回報截斷，由呼叫端改用保守判定——只回傳前 N 條等於
    靜默放行沒檢查到的路徑。
    """
    start = _unquoted_brace(text, mask)
    if start < 0:
        return [text], False
    end = _brace_close(text, mask, start)
    if end < 0:
        return [text], False
    alternatives = _brace_alternatives(text, mask, start, end)
    if len(alternatives) == 1:
        body_text, body_mask = alternatives[0]
        values = _brace_range(body_text) if "q" not in body_mask else None
        if values is None:
            # bash 對這種大括號原樣保留，只繼續展開後面的部分。
            tails, truncated = expand_braces(text[end + 1:], mask[end + 1:])
            return [text[:end + 1] + tail for tail in tails], truncated
        alternatives = [(value, "." * len(value)) for value in values]
    prefix = text[:start]
    suffix_text, suffix_mask = text[end + 1:], mask[end + 1:]
    results = []
    for alternative_text, alternative_mask in alternatives:
        expanded, truncated = expand_braces(
            alternative_text + suffix_text, alternative_mask + suffix_mask
        )
        if truncated:
            return results, True
        for item in expanded:
            results.append(prefix + item)
            if len(results) > BRACE_EXPANSION_LIMIT:
                return results, True
    return results, False


def _resolve(argument, cwds):
    """展開 brace 之後，相對路徑要對每個候選 cwd 各解析一次。"""
    mask = word_mask(argument)
    words, truncated = expand_braces(str(argument), mask)
    if truncated:
        # 超過上限就無法逐一檢查。任何比 repository scope 更窄的推測都要求
        # 「所有展開結果都在某個前綴底下」，而 .. 與切在元件中間的前綴都會
        # 讓那個前提不成立，因此直接退回整個 repository。
        words = ["."]
    resolved = []
    for word in words:
        if Path(word).is_absolute():
            resolved.append(word)
            continue
        resolved.extend(
            os.path.normpath(str(candidate / word)) for candidate in cwds
        )
    return resolved


def advance(cwds, destination, may_create, seed=None):
    """把候選 cwd 推進到 destination。

    目錄存在就必定成功、不存在就必定失敗；只有同一行內可能先建立目錄時，
    才同時保留兩條分支，且成功分支緊接在自己的失敗分支之前入列，
    截斷不會只留下其中一邊。
    """
    candidates = list(seed) if seed and may_create else []
    for candidate in cwds:
        reached = candidate / destination
        if reached.is_dir():
            candidates.append(reached)
        elif may_create:
            candidates.extend([reached, candidate])
        else:
            candidates.append(candidate)
    return list(dict.fromkeys(candidates))[:CWD_CANDIDATE_LIMIT]


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
    conditional = 0
    parts = re.split(r"([|;&\n\r]+|[<>]\(|\$\(|\)|`)", shell_command)
    for position, segment in enumerate(parts[::2]):
        separator = parts[2 * position - 1] if position else ""
        piped = "|" in separator
        if separator.strip() not in ("&&", "||", "|"):
            # [[ ]] 內部只可能出現 && ／ ||；其餘分隔符代表條件式已經結束，
            # 不重設就會讓一個沒閉合的 [[ 讓後續整行的重導向失去判定。
            conditional = 0
        tokens = split_tokens(segment)
        # 重導向可能出現在命令名之前（<file cat），所以掃整個 segment。
        # 重導向讓任何命令都讀得到檔案，與命令是不是 reader 無關。
        redirect_reads, redirect_writes, conditional = redirection_targets(
            segment, conditional
        )
        name, remaining, chdir = segment_command(tokens)
        operands = []
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
                cwds = advance(cwds, destination, may_create, [success_cwd, root])
        elif name in READ_COMMANDS:
            operands = path_operands(name, remaining)
        if (
            not operands
            and not redirect_reads
            and not piped
            and implicit_cwd_scope(name, remaining)
        ):
            # 這些 reader 不帶路徑時遞迴搜尋 cwd，那就是這次搜尋的 scope。
            operands = ["."]
        # prefix 造成的 chdir 只影響這一個命令，不改變後續 segment 的 cwd。
        segment_cwds = cwds
        if chdir:
            reached = [
                candidate / chdir
                for candidate in cwds
                if (candidate / chdir).is_dir()
            ]
            if reached:
                segment_cwds = reached
            elif may_create:
                segment_cwds = advance(cwds, chdir, may_create)
            else:
                # env -C 的目的地不存在時 env 直接失敗，被包裝的命令不會執行，
                # operand 一個都不會被讀到。重導向仍由 shell 先做，所以保留。
                operands = []
        for argument in operands:
            targets.extend(_resolve(argument, segment_cwds))
        # 重導向由 shell 在自己的 cwd 完成，不受 prefix chdir 影響。
        for argument in redirect_reads:
            targets.extend(_resolve(argument, cwds))
        for argument in redirect_writes:
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
