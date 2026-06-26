#!/usr/bin/env python3
# Why: context compaction 後 CLAUDE.md 的 path-scoped rules 不自動重注入。
# SessionStart(compact) 觸發時把關鍵 gate 規則重新注入 context。
import sys, pathlib

gate_summary = """
[STDD×VDD Gate Rules — reinject after compaction]
1. GATE:SPEC: 無 spec 不准寫實作（.vdd/phase 必須在 RED_VERIFIED 或 GREEN）
2. GATE:RED:  測試必須先失敗才能開始實作（存 .vdd/red/*.json）
3. GATE:GREEN: 所有測試必須通過才能結束（Stop hook 強制）
4. 實作 Agent 禁止弱化/刪除/skip 測試
5. VDD ≠ Value-Driven（純品質驗證層）
6. 查看 .vdd/phase 確認當前閘門狀態
7. 詳細規則參考 CLAUDE.md 和 docs/ 目錄
"""

print(gate_summary)
sys.exit(0)
