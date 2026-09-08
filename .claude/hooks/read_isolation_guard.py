#!/usr/bin/env python3
# Why: GATE:RED 的 agent_isolation_enforced 在 read 側的 runtime 落點。
# PreToolUse Read|Grep|Glob 觸發，依 .vdd/phase 決定哪一側不可讀：
#   implementation lane（RED_VERIFIED）：不得讀測試，避免對測試特化。
#   test-authoring lane（其他 phase）：不得讀實作，避免測試退化成實作的鏡子。
#   cycle_complete（GREEN）：cycle 已結束，不施加 read isolation；
#     下一輪 RED 驗證把 phase 轉回 RED_VERIFIED 時才重新武裝。
# Canonical Spec 兩側都必須可讀——它是雙方共同的約束來源。
import json
import sys
from pathlib import PurePosixPath

from path_policy import (
    PolicyError,
    classify_path,
    forbidden_side,
    isolated_side_exists,
    load_policy,
    read_lane,
    read_phase,
    red_evidence_root,
    scope_reaches_forbidden,
)

LANE_RULES = {
    "implementation": {
        "headline": "實作階段不得讀取測試檔",
        "why": (
            "  實作必須由 Canonical Spec 與 Red Evidence 推導。\n"
            "  讀得到測試，模型就能對測試特化而不解決需求。"
        ),
    },
    "test_authoring": {
        "headline": "測試撰寫階段不得讀取實作",
        "why": (
            "  測試必須由 Canonical Spec 推導。\n"
            "  讀得到實作，測試會退化成實作的鏡子，失去 falsification 能力。"
        ),
    },
}


WILDCARD_CHARS = "*?["


def text_field(tool_input, name):
    value = tool_input.get(name)
    return value if isinstance(value, str) and value else None


def literal_prefix(pattern):
    """回傳 pattern 中第一個 wildcard segment 之前的字面前綴。"""
    parts = []
    for part in PurePosixPath(pattern).parts:
        if any(character in part for character in WILDCARD_CHARS):
            break
        parts.append(part)
    return "/".join(parts)


def forbidden_target(tool_name, tool_input, policy, phase):
    """回傳 (target, reason)；None 代表放行。"""
    forbidden = forbidden_side(phase)
    if forbidden is None:
        return None

    if tool_name == "Read":
        value = text_field(tool_input, "file_path")
        if value and classify_path(value, policy) == forbidden:
            return value, "forbidden"
        return None

    base = text_field(tool_input, "path")
    if base:
        if classify_path(base, policy) == forbidden:
            return base, "forbidden"
        # path="." 分類是 other，卻涵蓋整個 repository；錨定必須排除這種 scope。
        if scope_reaches_forbidden(base, policy, forbidden):
            return base, "scope"

    # Glob 的 pattern 本身就是 path glob；Grep 的 glob 只是檔名 filter。
    pattern = text_field(tool_input, "pattern" if tool_name == "Glob" else "glob")
    prefix = literal_prefix(pattern) if pattern else ""
    if prefix:
        anchored = f"{base}/{prefix}" if base else prefix
        if classify_path(anchored, policy) == forbidden:
            return anchored, "forbidden"

    # 既沒有 path 也沒有字面前綴 → 例如 **/checks/**/*.py 或不帶 path 的 Grep。
    # 這種 pattern 能穿進被隔離的那一側，而 hook 無法證明它不會，因此保守擋下。
    if base is None and not prefix and isolated_side_exists(policy, forbidden):
        return (pattern or "<no path>"), "unanchored"
    return None


def main():
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    try:
        policy = load_policy()
        phase = read_phase()
        outcome = forbidden_target(tool_name, tool_input, policy, phase)
    except PolicyError as exc:
        print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
        return 2

    if outcome is None:
        return 0

    target, reason = outcome
    lane = read_lane(phase)
    rule = LANE_RULES[lane]
    if reason in ("unanchored", "scope"):
        detail = (
            "  這個 pattern 能穿進被隔離的一側，hook 無法證明它不會。"
            if reason == "unanchored"
            else "  這個 path 涵蓋了被隔離的一側。"
        )
        print(
            "BLOCKED [GATE:RED agent_isolation_enforced]: 未錨定的搜尋範圍。\n"
            f"  tool: {tool_name}\n"
            f"  scope: {target}\n"
            f"  phase: {phase!r}（lane={lane}）\n"
            f"{detail}\n"
            "  請以 path= 指定不含被隔離一側的搜尋根目錄，"
            "或給 pattern 一個字面前綴。",
            file=sys.stderr,
        )
        return 2

    escape = (
        f"  需要失敗細節請改讀 {red_evidence_root(policy)}/ 下的 Red Evidence"
        "（failure_message／failure_location）。\n"
        if lane == "implementation"
        else ""
    )
    print(
        f"BLOCKED [GATE:RED agent_isolation_enforced]: {rule['headline']}。\n"
        f"  tool: {tool_name}\n"
        f"  target: {target}\n"
        f"  phase: {phase!r}（lane={lane}）\n"
        f"{rule['why']}\n"
        f"{escape}"
        "  若這份 spec 無法在不看對側的情況下完成，回報並交由人工裁決，"
        "不要繞過本 guard。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
