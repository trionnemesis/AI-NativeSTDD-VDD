#!/usr/bin/env python3
# Why: GATE:RED 的 agent_isolation_enforced 在 read 側的 runtime 落點。
# PreToolUse Read|Grep|Glob 觸發，依 .vdd/phase 決定哪一側不可讀：
#   implementation lane（RED_VERIFIED／GREEN）：不得讀測試，避免對測試特化。
#   test-authoring lane（其他 phase）：不得讀實作，避免測試退化成實作的鏡子。
# Canonical Spec 兩側都必須可讀——它是雙方共同的約束來源。
import json
import sys

from path_policy import (
    IMPLEMENTATION_PHASES,
    PolicyError,
    load_policy,
    matches_test_path,
    path_in_roots,
    read_phase,
    red_evidence_root,
)

LANE_RULES = {
    "implementation": {
        "forbidden": "test",
        "headline": "實作階段不得讀取測試檔",
        "why": (
            "  實作必須由 Canonical Spec 與 Red Evidence 推導。\n"
            "  讀得到測試，模型就能對測試特化而不解決需求。"
        ),
    },
    "test_authoring": {
        "forbidden": "implementation",
        "headline": "測試撰寫階段不得讀取實作",
        "why": (
            "  測試必須由 Canonical Spec 推導。\n"
            "  讀得到實作，測試會退化成實作的鏡子，失去 falsification 能力。"
        ),
    },
}


def candidate_paths(tool_name, tool_input):
    """取出該 tool 可判定的 path-ish 輸入；判不出來的欄位一律不猜。"""
    if tool_name == "Read":
        values = [tool_input.get("file_path")]
    elif tool_name == "Glob":
        values = [tool_input.get("path"), tool_input.get("pattern")]
    elif tool_name == "Grep":
        values = [tool_input.get("path"), tool_input.get("glob")]
    else:
        values = []
    return [value for value in values if isinstance(value, str) and value]


def classify(value, policy):
    """把 path 分類；順序即優先權，用來解決 root 與 pattern 的重疊。

    只有 configured roots 內的路徑會被分類。roots 之外一律 "other"：
    setup protocol 明訂 policy 不得靠 framework heuristic 猜測，因此這裡也不猜
    ——否則 docs/02-canonical-spec.md 這種檔名含 spec 的文件會被當成測試擋掉。
    """
    if path_in_roots(value, policy["protected_spec_roots"]):
        return "spec"
    # 明確宣告的 test_roots 優先於 implementation_roots，支援 tests 內嵌於 app/ 的 layout。
    if path_in_roots(value, policy["test_roots"]):
        return "test"
    if path_in_roots(value, policy["implementation_roots"]):
        # 與實作同目錄的 test_file_patterns 命中者仍算測試側（例如 app/login.spec.ts）。
        return "test" if matches_test_path(value, policy) else "implementation"
    return "other"


def lane_for(phase):
    return "implementation" if phase in IMPLEMENTATION_PHASES else "test_authoring"


def forbidden_target(tool_name, tool_input, policy, phase):
    forbidden = LANE_RULES[lane_for(phase)]["forbidden"]
    for value in candidate_paths(tool_name, tool_input):
        if classify(value, policy) == forbidden:
            return value
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
        target = forbidden_target(tool_name, tool_input, policy, phase)
    except PolicyError as exc:
        print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
        return 2

    if target is None:
        return 0

    lane = lane_for(phase)
    rule = LANE_RULES[lane]
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
