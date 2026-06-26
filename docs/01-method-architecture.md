# 01 · 方法論架構（Method Architecture）

---

## 核心主張

STDD×VDD 是一套**以規格為核心、以驗證為終點**的 AI-native 工程治理體系。

傳統 TDD 的問題：AI agent 可以「通過測試而不解決真正的問題」。  
STDD 的解法：把 Canonical Spec 作為 **constraint**，測試只是 spec 的**機器可執行形式**。

---

## 5 層技術棧

```
┌──────────────────────────────────────────────┐
│  Layer 5: Production Telemetry（最終仲裁）      │  ← GATE:DEPLOY
├──────────────────────────────────────────────┤
│  Layer 4: VDD Verification（品質驗證）          │  ← GATE:VDD
├──────────────────────────────────────────────┤
│  Layer 3: Green（實作完成）                     │  ← GATE:GREEN
├──────────────────────────────────────────────┤
│  Layer 2: Red（測試先行）                       │  ← GATE:RED
├──────────────────────────────────────────────┤
│  Layer 1: Canonical Spec（規格約束）            │  ← GATE:SPEC
└──────────────────────────────────────────────┘
                    ↑ GATE:ADMIT（上游探索）
```

---

## 方法論比較表

| 維度 | 傳統 TDD | BDD | STDD×VDD |
|------|---------|-----|---------|
| 起點 | 測試 | 行為描述 | **Canonical Spec（有 Stable ID）** |
| AI 約束 | 無 | 弱 | **硬約束（hook runtime 強制）** |
| 規格追蹤 | 無 | 部分 | **全鏈路 Stable ID** |
| 偽測試防護 | 無 | 無 | **Red Evidence + 突變測試** |
| 變更管理 | 無 | 無 | **Delta Spec 套件** |
| 驗證終點 | 測試通過 | 測試通過 | **Production Telemetry** |
| AI Agent 適配 | 差 | 中 | **專門設計** |

---

## 核心設計原則

### 原則 1：Spec First，永遠先寫規格

```
需求 → Canonical Spec（REQ: + BDD:）→ 測試（紅）→ 實作 → 通過（綠）→ VDD 驗證
```

沒有規格，agent 不允許寫任何 `src/` 下的檔案。

### 原則 2：Red Evidence 不可偽造

AI agent 的常見失敗模式：直接寫「通過的測試」，從未讓測試失敗。  
Red Evidence 機制：測試執行失敗的 stdout 必須以 JSON 格式儲存，作為不可否認的紀錄。

### 原則 3：VDD 是品質，不是安全漏洞偵測

VDD 閘門的職責：
- 覆蓋率指標（≥ 80%）
- 突變測試（確保測試有效）
- 整合測試（系統邊界）
- Contract Testing（API 相容性）

不是：安全掃描、效能測試（雖可包含）

### 原則 4：Telemetry 是最終仲裁者

所有 Gate 通過只代表「在已知條件下正確」。  
Production Telemetry 才能確認「在真實流量下正確」。

---

## Domain-Driven Design 整合

STDD×VDD 完全相容 DDD：

| DDD 概念 | STDD×VDD 對應 |
|---------|--------------|
| Bounded Context | `specs/domain/<context>/` |
| Aggregate | `specs/domain/<entity>.yaml` 的 `aggregate:` 欄位 |
| Domain Event | `SIG:` namespace |
| Ubiquitous Language | `TERM:` namespace |

---

## Autonomy Tiers 決策樹

```
新任務進入
    ↓
是否涉及 schema migration / auth / pricing？
    ↓ YES → T3（禁止 auto-dispatch）
    ↓ NO
是否有規格變更或新 domain entity？
    ↓ YES → T2（auto-PR + human review）
    ↓ NO
是否純文件/非破壞性修復？
    ↓ YES → T1（auto-PR）
    ↓ NO（不確定）→ T2（預設）
```

---

*本章對應 Notion 頁面 01 · 方法論架構*
