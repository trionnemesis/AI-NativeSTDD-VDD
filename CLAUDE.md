# STDD×VDD Claude Code 治理指令

> **這是 AI-Native STDD×VDD 工程治理系統的 agent 指令檔。**  
> Claude Code agent 在任何套用此框架的專案中，必須嚴格遵守以下規則。

> **Authority state（MCR:2026:004）**：先讀 `governance/manifest.yaml`。目前 repo 是 `SHADOW_NON_AUTHORITATIVE`，Notion 仍為 canonical；本檔是相容性摘要。衝突時必須 loud fail，不得自行把 repo shadow 升格。

---

## 一、啟動流程

首次進入專案時，**必須先讀 `governance/manifest.yaml`，再讀 `setup/AGENT_SETUP_PROTOCOL.md` 並執行 Confirm Mode**。

```
FIRST ACTION: 讀 governance/manifest.yaml → 依任務載入 gate/profile → 閱讀 setup/AGENT_SETUP_PROTOCOL.md → 執行 Confirm Mode
```

---

## 二、Glossary compatibility summary

Machine-readable shadow 位於 `governance/glossary.yaml`；以下只保留舊版相容性摘要，不得取代完整 glossary 或 Notion authority。

| 術語 | 定義 |
|------|------|
| **STDD** | Specification & Test-Driven Development：以 Canonical Spec + 先寫測試作為 hard constraint |
| **VDD** | Verification & Validation-Driven Development（**≠ Value-Driven，≠ Vulnerability-Driven**）：Green 後的 profile-resolved quality gate；Production Telemetry 僅驗證 operational quality assumptions，不是 security/privacy/authorization/compliance 的唯一證據 |
| **Canonical Spec** | `.vdd/path-policy.json` 的 `protected_spec_roots` 所宣告之單一規格來源，包含 Stable ID；相容預設為 `spec/`、`specs/` |
| **Red Evidence** | `red_evidence_template` 所宣告的 JSON evidence；相容預設為 `.vdd/red/<module>.json` |
| **Delta Spec** | 變更套件，包含 intent.md、delta.yaml、impact.md、acceptance.feature |
| **Headroom** | Context 壓縮層，token 效率中介層（≠ memory engine） |

---

## 三、5 規範閘門（禁止跳過）

```
GATE:SPEC → GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY
```

上游 `GATE:ADMIT` 把 Signal 經 deterministic admission、tiered dispatch 與 provenance 轉為 Change Intent；它不屬五道 Gate。`GATE:REGRESSION` 是 agent workflow configuration 的 auxiliary gate，也不改變此序列。

### GATE:SPEC（runtime 強制）
- **條件**：Change Intent、Delta Spec、Impact Analysis、Stable ID、System／Change Profile、適用 assertion 與 evidence plan 已解析
- **強制**：已安裝 target 的 PreToolUse hook 依 `.vdd/path-policy.json` 阻擋 protected spec 寫入，以及缺少對應 feature spec 的 configured implementation-root 寫入；其他 contract 是否 enforcement 以 Confirm Mode 與 target policy 為準
- **禁止**：無 spec 寫任何 configured implementation root 下的實作檔

### GATE:RED（runtime 強制）
- **條件**：FEATURE／DEFECT 有 baseline failure；其他 Change Profile 有 policy-accepted alternative evidence
- **強制**：PreToolUse hook
- **禁止**：測試或替代 evidence 無失敗能力就開始實作；test actor 不可讀取新的 implementation solution
- **必做**：主 agent 提供 requirement／implementation／test mapping 與 policy-resolved evidence path，委派 `red-verifier` 真實 collect/run 後寫入 evidence 與 `.vdd/phase`

### GATE:GREEN（runtime 強制）
- **條件**：profile-resolved tests、static analysis、lint/type/build、protected-test integrity 均通過；啟用 TIA 時保留 selection/fallback evidence
- **強制**：已安裝 target 的 Stop hook 對 configured `test_roots` 執行 pytest，再執行 `ruff check .`；path policy 不接受 repository-defined executable
- **禁止**：弱化/跳過/刪除測試以繞過此閘門

### GATE:VDD（config/流程）
- **條件**：適用的 mutation、performance、reliability、resilience、negative path、a11y/visual、security/privacy/authorization evidence 完整
- **強制**：profile policy、Evidence Envelope 與 target CI/runner；不存在 single universal coverage/tool threshold
- **產出**：可重跑的 quality evidence；waiver 必須有效、有限期且獨立核准

### GATE:DEPLOY（架構性外建）
- **條件**：Release Profile、migration compatibility、controlled rollout、observation window、promotion/abort/rollback、supply-chain evidence 與 runbook 就緒
- **說明**：這是發布**前**的 deployability gate；發布後的 Production Verification 仍需外建監控與 Evidence Envelope

---

## 四、絕對禁止行為（No-Go）

以下行為在任何情況下都不允許：

1. **無 spec 寫實作** → 先依 `feature_spec_templates` 建立對應 spec
2. **跳過 RED Gate** → 必須有 `red_evidence_template` 對應的 JSON evidence
3. **弱化測試**：
   - `assert True`（無效斷言）
   - `pytest.skip` / `unittest.skip`（跳過測試）
   - `xfail`（預期失敗標記）
   - `pass # assert`（空斷言）
4. **直接刪除測試** → 測試刪除需 spec 更新作為前提
5. **用 Bash 繞過 hook**（對 configured implementation roots 使用 redirect、`tee`、`sed -i` 等）
6. **在 T3 需求下 auto-dispatch**

---

## 五、Autonomy Tiers

| Tier | 行為 | 適用場景 |
|------|------|---------|
| **T1** | auto-dispatch + draft/propose PR | low-severity `dependency_patch`、`lint`、`doc_drift`；先通過 worktree attestation，仍不得 direct merge |
| **T2**（預設） | auto-dispatch + draft PR + 強制 human review | bug/performance regression 且不觸及 invariant；所有未命中 T1/T3 的情況 |
| **T3** | human-written Change Intent；禁止 auto-dispatch | touches invariant、security、schema migration 或 uncorroborated high severity |

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
| `EVID:` | Evidence Envelope records |
| `TERM:` | Glossary terms |

---

## 七、Hook 強制等級

| 等級 | 說明 | 範例 |
|------|------|------|
| **runtime 強制** | hook/harness，模型不可繞過 | Stop hook, PreToolUse exit 2 |
| **config/流程** | 狀態機，有條件可繞 | `.vdd/phase` |
| **deterministic policy** | ruleset／profile resolver／admission contract，LLM 不得作唯一裁決 | dedup、tier assignment、assertion applicability |
| **prompt-only** | 提示層，不保證遵從 | spec 語意正確性 |
| **架構性外建** | Claude Code 做不到 | Telemetry 閉環 |

---

## 八、Worktree Isolation

- **Plane A**（Worktree）：correctness boundary，每個 subagent 獨立 worktree
- **Plane B**（Sandbox）：OS-level FS/network，process-level 非 per-subagent

---

## 九、Definition of Ready（實作前前提）

1. Change Intent、System／Change Profile、risk tier 與 assertion applicability 已解析。
2. Delta Spec、Impact Analysis、Stable IDs 和適用 domain/BDD/UI/API/quality/release contract 已核准。
3. acceptance criteria 與 Evidence Envelope 可機器驗證。
4. 相容性、migration、deprecation、consumer impact 與 Release Profile 已分類。
5. FEATURE／DEFECT 有 Red Evidence；其他 Change Profile 有 policy-accepted alternative evidence。
6. `.vdd/phase = RED_VERIFIED` 僅是已安裝 Claude Code hook 的相容性狀態，不取代完整 profile/evidence contract。

---

## 十、Context Compaction 後規則重注入

Context 被壓縮後，`SessionStart(compact)` hook 會自動重注入關鍵閘門規則。  
若未收到重注入，主動讀取本檔案確認規則。

---

## 十一、相關文件

- Authority state：`governance/manifest.yaml`
- Target path policy：`.vdd/path-policy.json`（不存在時使用 compatibility defaults；格式錯誤時 loud fail）
- Task-specific machine contracts：`governance/gates/`、`governance/profiles/`
- Human reference：`docs/` 目錄
- Agent 設定：`setup/AGENT_SETUP_PROTOCOL.md`
- 原始規格：https://www.notion.so/AI-Native-STDD-VDD-382f5b2d1a9081e9a972f0b33fad3142
