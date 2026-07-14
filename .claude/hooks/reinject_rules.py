#!/usr/bin/env python3
# Why: context compaction 後 CLAUDE.md 的 path-scoped rules 不自動重注入。
# SessionStart(compact) 觸發時把關鍵 gate 規則重新注入 context。
import sys

from path_policy import PolicyError, load_policy


try:
    policy = load_policy()
except PolicyError as exc:
    print(f"BLOCKED [PATH POLICY]: {exc}", file=sys.stderr)
    sys.exit(2)

implementation_roots = ", ".join(policy["implementation_roots"])
test_roots = ", ".join(policy["test_roots"])
red_evidence_template = policy["red_evidence_template"]
gate_summary = f"""
[STDD×VDD Gate Rules — reinject after compaction]
1. GATE:SPEC: 無 spec 不准寫 configured implementation roots: {implementation_roots}
2. GATE:RED:  測試必須先失敗；evidence path template: {red_evidence_template}
3. GATE:GREEN: pytest roots ({test_roots}) 與 ruff 全數通過才能結束（Stop hook 強制）
4. 實作 Agent 禁止弱化/刪除/skip 測試
5. VDD ≠ Value-Driven（純品質驗證層）
6. 查看 .vdd/phase 確認當前閘門狀態
7. 詳細規則參考 .vdd/path-policy.json、CLAUDE.md 和 docs/ 目錄
"""

print(gate_summary)
sys.exit(0)
