# 11 · Headroom Context 壓縮層（Headroom Context Compression）

---

## 定義（重要）

> **Headroom = Context 壓縮層（token 效率中介層），≠ memory engine，≠ 長期記憶儲存**

Headroom 解決的問題：Claude Code session 的 context window 有限，長 session 會因 context 壓縮而遺失關鍵治理規則。

---

## 問題陳述

Claude Code 的 context compaction 機制：
- 當 context 接近上限時，舊訊息被自動摘要壓縮
- 壓縮後，CLAUDE.md 的 **path-scoped rules 不會自動重注入**
- 導致 agent 在長 session 中「忘記」閘門規則

---

## Headroom 設計目標

```
保留: 當前任務的關鍵上下文
壓縮: 已完成步驟的詳細輸出
重注入: 治理規則（GATE:SPEC, GATE:RED, etc.）
```

---

## 技術實作：SessionStart(compact) Hook

`reinject_rules.py` 在 context compaction 觸發後執行：

```python
#!/usr/bin/env python3
# Why: context compaction 後 CLAUDE.md 的 path-scoped rules 不自動重注入。
import sys, pathlib

gate_summary = """
[STDD×VDD Gate Rules — reinject after compaction]
1. GATE:SPEC: 無 spec 不准寫實作（.vdd/phase 必須在 RED_VERIFIED 或 GREEN）
2. GATE:RED:  測試必須先失敗才能開始實作（存 .vdd/red/*.json）
3. GATE:GREEN: 所有測試必須通過才能結束（Stop hook 強制）
4. 實作 Agent 禁止弱化/刪除/skip 測試
5. VDD ≠ Value-Driven（純品質驗證層）
"""

print(gate_summary)
sys.exit(0)
```

SessionStart(compact) 是 Claude Code 在完成 context compaction 後觸發的 hook event，`stdout` 內容會注入新的 context。

---

## UserPromptSubmit Hook：Spec 狀態注入

`inject_spec.py` 在每次使用者輸入時執行，注入當前狀態：

```python
# 注入當前 .vdd/phase 狀態
phase_file = pathlib.Path(".vdd/phase")
if phase_file.exists():
    phase = phase_file.read_text().strip()
    output_lines.append(f"[STDD×VDD] Current gate phase: {phase}")

# 注入最近 spec 變更摘要
result = subprocess.run(
    ["git", "diff", "--name-only", "--", "spec/", "specs/"],
    ...
)
```

---

## Headroom 設計原則

### 原則 1：規則注入，不儲存歷史

Headroom **不是記憶系統**。它不儲存：
- 過去的實作細節
- 歷史測試結果
- 已完成需求的上下文

它只注入：
- 當前 phase 狀態
- 核心閘門規則（在 compaction 後）
- 修改中的 spec 摘要

### 原則 2：Runtime 規則優先於 Prompt 注入

```
優先序:
1. Hook 強制（exit 2）         ← 最強，模型無法繞過
2. managed-settings.json deny  ← 第二強
3. SessionStart 重注入          ← 對抗 compaction
4. UserPromptSubmit 注入        ← 每次 prompt 前置
5. CLAUDE.md prompt 規則       ← 最弱，可被 compaction 丟失
```

### 原則 3：關鍵不變量不依賴 context

GATE:SPEC 和 GATE:RED 的強制不依賴 agent 記住規則，而是依賴 hook 的 exit 2。即使 context 完全被壓縮，hook 仍然有效。

---

## Context Budget 管理建議

長 session 中的 token 消耗管理：

```markdown
當 session 接近 context 上限時:
1. 完成當前 GATE 再結束（不要在 RED_VERIFIED 和 GREEN 中間結束）
2. 確認 .vdd/phase 已正確更新（狀態不在 context 中，在檔案中）
3. Red Evidence 已存入 .vdd/red/（不在 context 中，在檔案中）
4. 下個 session 開始前確認 .vdd/phase 狀態
```

---

## 與 Memory 系統的區別

| | Headroom | Memory（~/.claude/memory/）|
|---|---------|--------------------------|
| **目的** | Token 效率，規則持久性 | 跨 session 的使用者偏好/專案上下文 |
| **儲存** | 不儲存，只注入 | 長期檔案 |
| **範圍** | 當前 session | 跨所有 session |
| **觸發** | Hook 自動 | 明確寫入 |
| **STDD×VDD 角色** | Gate 規則重注入 | 專案層面的學習 |

---

*本章對應 Notion 頁面 11 · Headroom Context 壓縮層*
