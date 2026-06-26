# 08 · 業界方法論比較（Industry Comparison）

---

## 概述

本章從 12 個維度分析 STDD×VDD 與現有主流方法論的差異，並識別採用時的優勢與缺口。

---

## 12 維度比較矩陣

| 維度 | TDD | BDD | SAFe | XP | STDD×VDD |
|------|-----|-----|------|-----|---------|
| **D1 規格形式化** | 無 | 部分（Gherkin）| 弱 | 弱 | **強（Stable ID + yaml）** |
| **D2 AI Agent 約束** | 無 | 無 | 無 | 無 | **runtime hook 強制** |
| **D3 偽測試防護** | 無 | 無 | 無 | 無 | **Red Evidence + 突變測試** |
| **D4 變更追蹤** | 無 | 無 | Jira（鬆） | 無 | **Delta Spec 套件** |
| **D5 UI 狀態契約** | 無 | 部分 | 無 | 無 | **UI State Contract** |
| **D6 Contract Testing** | 無 | 無 | 無 | 部分 | **Pact 整合** |
| **D7 可追溯性** | 低 | 中 | 高（重） | 低 | **全鏈路 Stable ID** |
| **D8 Context 管理** | N/A | N/A | N/A | N/A | **Headroom 壓縮層** |
| **D9 閘門自動化** | 低 | 低 | 中 | 中 | **runtime + CI 自動** |
| **D10 學習曲線** | 低 | 中 | 高 | 中 | **高（初期設定重）** |
| **D11 工具依賴** | 低 | 中 | 高 | 中 | **中（Python + pytest + ruff）** |
| **D12 Telemetry 整合** | 無 | 無 | 弱 | 無 | **設計目標（架構外建）** |

---

## 團隊優勢識別（基於當前實踐）

採用 STDD×VDD 的團隊通常在以下維度已有基礎：

### 強項（已有基礎）
- **D1 規格形式化**：若已有 OpenAPI / Gherkin 習慣，遷移成本低
- **D2 AI Agent 約束**：Claude Code hook 機制完整
- **D4 變更追蹤**：Git-native Delta Spec，不依賴 Jira
- **D5 UI State Contract**：前端組件化架構中易實作
- **D6 Contract Testing**：Pact 生態成熟

### 常見缺口（需特別投資）
- **D10 學習曲線**：需要 spec 優先的思維轉變
- **D12 Telemetry 整合**：多數團隊監控基礎設施不完整

---

## 方法論適用場景

### STDD×VDD 最適合

```
✅ AI agent 深度參與開發的專案
✅ 規格需頻繁變更的產品（Delta Spec 管理）
✅ 多個 AI agent 並行工作（worktree isolation）
✅ 品質要求高、需機器可驗證的系統
✅ 需要完整稽核軌跡的合規場景
```

### STDD×VDD 可能 overkill 的場景

```
⚠️ 純 prototype / throwaway code
⚠️ 單人小型 side project（setup 成本 > 收益）
⚠️ 純 ETL / 批次腳本（無複雜業務邏輯）
```

---

## 與 Shift-Left Testing 的關係

Shift-Left 的核心主張：越早發現問題越便宜。  
STDD×VDD 的 Shift-Further-Left：

```
傳統:  需求 → 實作 → 測試 → 部署 → 問題發現
TDD:   需求 → [測試 → 實作] → 部署 → 問題發現
STDD:  需求 → [Spec → 測試(RED) → 實作 → GREEN] → VDD → 部署 → Telemetry
```

STDD 把規格驗證也 shift-left，不只是測試。

---

## 與 SAFe / Scaled Agile 的整合

STDD×VDD 可作為 SAFe 的技術實踐層：

| SAFe 層 | STDD×VDD 對應 |
|---------|--------------|
| Epic / Feature | GATE:ADMIT（探索分派）|
| Story / AC | Canonical Spec + BDD scenarios |
| Sprint | GATE:SPEC → GATE:RED → GATE:GREEN |
| System Demo | GATE:VDD Report |
| Release | GATE:DEPLOY + Telemetry |

---

## 競爭分析：AI-Native 開發框架

| 框架 | AI 約束機制 | Spec-First | 偽測試防護 | 成熟度 |
|------|------------|------------|-----------|--------|
| GitHub Copilot + TDD | 無 | 無 | 無 | 高 |
| Cursor | 無（Rules 僅 prompt）| 無 | 無 | 中 |
| Devin | 弱（內建） | 無 | 無 | 低 |
| **STDD×VDD** | **runtime hook** | **強** | **Red Evidence** | **設計完整** |

---

*本章對應 Notion 頁面 08 · 業界方法論比較*
