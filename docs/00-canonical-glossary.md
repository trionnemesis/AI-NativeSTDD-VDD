# 00 · Canonical Glossary（術語權威定義）

> **唯一來源原則**：本文件是所有術語的唯一定義位置。其他文件的術語以此為準，矛盾時本文件優先。

---

## 核心方法論

| TERM ID | 術語 | 定義 | 禁止混淆 |
|---------|------|------|---------|
| `TERM:STDD` | **STDD** | Specification & Test-Driven Development：以 Canonical Spec + 先寫失敗測試作為 hard constraint，限制 AI agent 的實作範圍 | ≠ TDD（無 spec 層）|
| `TERM:VDD` | **VDD** | **Verification & Validation-Driven Development**：Green 後的機器可驗證品質閘門體系，最終仲裁者是 Production Telemetry | **≠ Value-Driven Development**、**≠ Vulnerability-Driven Development** |
| `TERM:DDD` | **DDD** | Domain-Driven Design（標準定義） | — |
| `TERM:BDD` | **BDD** | Behavior-Driven Development（標準定義） | — |
| `TERM:DI` | **DI** | Dependency Injection（標準定義） | — |

---

## 規格與 ID 系統

| TERM ID | 術語 | 定義 |
|---------|------|------|
| `TERM:CANONICAL_SPEC` | **Canonical Spec** | `specs/` 目錄下的單一規格來源；所有 REQ/BDD/API/UI 的主檔 |
| `TERM:STABLE_ID` | **Stable ID** | 永不重用的命名空間前綴 ID，格式：`NAMESPACE:identifier` |
| `TERM:DELTA_SPEC` | **Delta Spec** | 變更套件，包含 intent.md + delta.yaml + impact.md + acceptance.feature + verification-plan.yaml |
| `TERM:RED_EVIDENCE` | **Red Evidence** | `.vdd/red/<req-id>.json`，機器可驗證的「測試在實作前失敗」紀錄 |

---

## Stable ID 命名空間表

| Prefix | 含義 | 範例 |
|--------|------|------|
| `TERM:` | Glossary 術語 | `TERM:VDD` |
| `GATE:` | 閘門 | `GATE:RED` |
| `REQ:` | Requirements | `REQ:AUTH-001` |
| `INV:` | Invariants（不可違背約束） | `INV:SPEC-FIRST` |
| `BDD:` | BDD scenarios | `BDD:LOGIN-001` |
| `API:` | API contracts | `API:USER-V2` |
| `UI:` | UI state contracts | `UI:LOGIN-FORM` |
| `QP:` | Quality policies | `QP:COVERAGE-80` |
| `ADR:` | Architecture decisions | `ADR:001` |
| `CR:` | Change requests | `CR:2026-007` |
| `SIG:` | Signal/telemetry events | `SIG:USER_SIGNUP` |
| `ADMIT:` | Discovery items | `ADMIT:001` |
| `WT:` | Worktree IDs | `WT:feature-auth` |
| `ATTEST:` | Attestation records | `ATTEST:CR-007-VDD` |

---

## 閘門（Gates）

| TERM ID | 術語 | 定義 | 強制等級 |
|---------|------|------|---------|
| `GATE:ADMIT` | Discovery Gate | 任何需求進入 GATE:SPEC 前的探索分派循環（上游閘門） | prompt-only |
| `GATE:SPEC` | Spec Gate | 寫實作前必須有 `.feature` 檔 | **runtime 強制** |
| `GATE:RED` | Red Gate | 實作前測試必須失敗，存 Red Evidence | **runtime 強制** |
| `GATE:GREEN` | Green Gate | 所有測試通過 + lint clean | **runtime 強制（Stop hook）** |
| `GATE:VDD` | VDD Gate | 覆蓋率 + 突變測試 + 整合測試 | config/流程 |
| `GATE:DEPLOY` | Deploy Gate | Production Telemetry 閉環確認 | 架構性外建 |

---

## 隔離層

| TERM ID | 術語 | 定義 |
|---------|------|------|
| `TERM:PLANE_A` | Worktree Isolation（Plane A） | per-subagent git worktree，correctness boundary |
| `TERM:PLANE_B` | Sandbox Isolation（Plane B） | OS-level FS/network，process-level（非 per-subagent） |

---

## AI Agent 行為

| TERM ID | 術語 | 定義 |
|---------|------|------|
| `TERM:T1` | Autonomy T1 | 自動 PR，無須人工介入 |
| `TERM:T2` | Autonomy T2（預設） | 自動 PR + 強制 human review |
| `TERM:T3` | Autonomy T3 | 禁止 auto-dispatch |
| `TERM:HEADROOM` | Headroom | Context 壓縮層（token 效率中介層）；**≠ memory engine** |
| `TERM:DEFINITION_OF_READY` | Definition of Ready | 進入實作前必須滿足的 6 項前提條件 |
| `TERM:MUTATION_TESTING` | Mutation Testing | 對已變更程式碼 + critical domain 執行突變測試；escaped mutant 需 disposition 紀錄 |

---

## 禁止混淆一覽

1. **VDD ≠ Value-Driven** — VDD 純粹是品質驗證層
2. **VDD ≠ Vulnerability-Driven** — 安全掃描是 VDD 的子集，不是全部
3. **Headroom ≠ memory** — Headroom 是 token 壓縮，不儲存長期記憶
4. **Plane A ≠ security boundary** — Worktree 是 correctness 邊界，安全邊界是 Plane B
5. **GATE:ADMIT ≠ GATE:SPEC 的一部分** — ADMIT 是上游獨立閘門

---

*本文件版本：2026-06-26*
