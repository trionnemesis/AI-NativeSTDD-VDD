# STDD×VDD Claude Code 治理指令

> **這是 AI-Native STDD×VDD 工程治理系統的 agent 指令檔。**  
> Claude Code agent 在任何套用此框架的專案中，必須嚴格遵守以下規則。

---

## 一、啟動流程

首次進入專案時，**必須先讀 `setup/AGENT_SETUP_PROTOCOL.md` 並執行 Confirm Mode**。

```
FIRST ACTION: 閱讀 setup/AGENT_SETUP_PROTOCOL.md → 執行 Confirm Mode 清單
```

---

## 二、Canonical Glossary（術語定義）

以下定義為本專案唯一權威。所有歧義以此為準。

| 術語 | 定義 |
|------|------|
| **STDD** | Specification & Test-Driven Development：以 Canonical Spec + 先寫測試作為 hard constraint |
| **VDD** | Verification & Validation-Driven Development（**≠ Value-Driven，≠ Vulnerability-Driven**）：Green 後機器可驗證的品質閘門 |
| **Canonical Spec** | `specs/` 下的單一規格來源，包含 Stable ID |
| **Red Evidence** | `.vdd/red/<req-id>.json`，證明測試在實作前失敗 |
| **Delta Spec** | 變更套件，包含 intent.md、delta.yaml、impact.md、acceptance.feature |
| **Headroom** | Context 壓縮層，token 效率中介層（≠ memory engine） |

---

## 三、5 規範閘門（禁止跳過）

```
GATE:SPEC → GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY
```

上游閘門（`GATE:ADMIT`）：任何需求在進入 GATE:SPEC 前必須通過探索分派循環。

### GATE:SPEC（runtime 強制）
- **條件**：對應 `specs/features/<module>.feature` 必須存在且非空
- **強制**：PreToolUse hook，`sys.exit(2)` 阻擋 Edit/Write
- **禁止**：無 spec 寫任何 `src/` 下的實作檔

### GATE:RED（runtime 強制）
- **條件**：`.vdd/phase` 必須為 `RED_VERIFIED`
- **強制**：PreToolUse hook
- **禁止**：測試未失敗就開始實作
- **必做**：委派 `red-verifier` subagent 執行，存 `.vdd/red/<req-id>.json`

### GATE:GREEN（runtime 強制）
- **條件**：`pytest tests/` 全通過 + `ruff check .` clean
- **強制**：Stop hook，未通過無法結束 session
- **禁止**：弱化/跳過/刪除測試以繞過此閘門

### GATE:VDD（config/流程）
- **條件**：覆蓋率 ≥ 80%、突變測試通過、整合測試綠燈
- **強制**：`.vdd/phase` 狀態機
- **產出**：VDD Report（`docs/vdd-report.md`）

### GATE:DEPLOY（架構性外建）
- **條件**：Production Telemetry 閉環確認（Claude Code 無法強制）
- **說明**：需外建監控系統

---

## 四、絕對禁止行為（No-Go）

以下行為在任何情況下都不允許：

1. **無 spec 寫實作** → 先建 `specs/features/<module>.feature`
2. **跳過 RED Gate** → 必須有 `.vdd/red/*.json` 作為 evidence
3. **弱化測試**：
   - `assert True`（無效斷言）
   - `pytest.skip` / `unittest.skip`（跳過測試）
   - `xfail`（預期失敗標記）
   - `pass # assert`（空斷言）
4. **直接刪除測試** → 測試刪除需 spec 更新作為前提
5. **用 Bash 繞過 hook**（`echo > src/`、`tee`、`sed -i`）
6. **在 T3 需求下 auto-dispatch**

---

## 五、Autonomy Tiers

| Tier | 行為 | 適用場景 |
|------|------|---------|
| **T1** | 自動 PR，無 review | 文件更新、非破壞性修復 |
| **T2**（預設） | 自動 PR + 強制 human review | 規格變更、新功能 |
| **T3** | 禁止 auto-dispatch | schema migration、auth、pricing |

**fallthrough = T2**。不確定時一律 T2。

---

## 六、Stable ID 命名空間

| Prefix | 用途 |
|--------|------|
| `REQ:` | Requirements |
| `GATE:` | 閘門 |
| `INV:` | Invariants |
| `BDD:` | BDD scenarios |
| `API:` | API contracts |
| `UI:` | UI contracts |
| `QP:` | Quality policies |
| `ADR:` | Architecture decisions |
| `CR:` | Change requests |
| `SIG:` | Signal/telemetry |
| `ADMIT:` | Discovery items |
| `WT:` | Worktree IDs |
| `ATTEST:` | Attestation records |
| `TERM:` | Glossary terms |

---

## 七、Hook 強制等級

| 等級 | 說明 | 範例 |
|------|------|------|
| **runtime 強制** | hook/harness，模型不可繞過 | Stop hook, PreToolUse exit 2 |
| **config/流程** | 狀態機，有條件可繞 | `.vdd/phase` |
| **prompt-only** | 提示層，不保證遵從 | spec 語意正確性 |
| **架構性外建** | Claude Code 做不到 | Telemetry 閉環 |

---

## 八、Worktree Isolation

- **Plane A**（Worktree）：correctness boundary，每個 subagent 獨立 worktree
- **Plane B**（Sandbox）：OS-level FS/network，process-level 非 per-subagent

---

## 九、Definition of Ready（實作前 6 項前提）

1. `specs/features/<module>.feature` 存在且非空
2. `specs/domain/<entity>.yaml` 定義 domain entity
3. acceptance criteria 可機器驗證
4. 相依 API contract 已鎖版
5. T1/T2/T3 tier 已確認
6. `.vdd/phase = RED_VERIFIED`（由 red-verifier 驗證）

---

## 十、Context Compaction 後規則重注入

Context 被壓縮後，`SessionStart(compact)` hook 會自動重注入關鍵閘門規則。  
若未收到重注入，主動讀取本檔案確認規則。

---

## 十一、相關文件

- 完整規格：`docs/` 目錄下 14 個章節
- Agent 設定：`setup/AGENT_SETUP_PROTOCOL.md`
- 原始規格：https://www.notion.so/AI-Native-STDD-VDD-382f5b2d1a9081e9a972f0b33fad3142
