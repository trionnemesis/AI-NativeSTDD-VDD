# 00 · Canonical Glossary（術語權威定義）

> **Authority boundary**：此頁是 repository human reference。唯一 canonical glossary 是 [Notion root page](https://www.notion.so/AI-Native-STDD-VDD-382f5b2d1a9081e9a972f0b33fad3142)；machine-readable shadow 位於 [`governance/glossary.yaml`](../governance/glossary.yaml)。衝突時以 Notion 為準，shadow 不代表已 cutover。

## 使用規則

- 所有縮寫只依 Canonical Glossary 解析；不得以模型先驗或業界常見展開取代 project-local 定義。
- 每個術語以 Stable ID 定義一次；其他文件只能引用 ID，不重新定義語意。
- `VDD` 與 `STDD` 不是通用業界縮寫。對外新文件可使用 `V&V-DD`，避免與其他 VDD 展開混淆。

## 核心方法論

| Stable ID | 術語 | Canonical meaning |
|---|---|---|
| `TERM:STDD` | **Specification & Test-Driven Development** | 以 Canonical Spec + Test 作為 hard constraint；AI 實作不得超出 spec 與測試界定的行為集合。 |
| `TERM:VDD` | **Verification & Validation-Driven Development** | Green 後對品質屬性執行 machine-checkable verification；部署後以 Production Telemetry 驗證 operational quality assumptions。 |
| `TERM:DDD` | Domain-Driven Design | 定義業務邊界、ubiquitous language 與 domain invariants。 |
| `TERM:BDD` | Behavior-Driven Development | 用 Given-When-Then 定義使用者可觀察行為與 acceptance scenarios。 |
| `TERM:DI` | Dependency Injection | 讓依賴可替換、元件可隔離、測試可成立。 |
| `TERM:UI-STATE` | UI State Contract | 補足 Loading、Error、Empty、Disabled 等互動狀態契約。 |

`VDD` 不是 Value-Driven Development，也不是 Vulnerability-Driven Development。Production Telemetry 不是 security、privacy、authorization 或 compliance 的唯一證明；這些領域仍需 policy、design review、scan、attestation 與獨立裁決。

## Discovery、隔離與交付效率

| Stable ID | 術語 | Canonical meaning |
|---|---|---|
| `TERM:SIGNAL` | Discovery Signal | 來自 CI、Telemetry、SCA/CVE、dependency、drift 或人工 issue 的原始事件；必含 fingerprint。 |
| `TERM:ADMISSION` | Admission Control | 將 triaged signal 升級為 Change Intent 前的 deterministic 准入裁決；LLM 不得是唯一裁決者。 |
| `TERM:AUTONOMY-TIER` | Autonomy Tier | T1 auto-PR、T2 auto-PR + human review、T3 human Change Intent + no auto-dispatch 的 deterministic 分級。 |
| `TERM:DISPATCH` | Dispatch Assignment | `subagent role × worktree × time/token budget` 的派工綁定。 |
| `TERM:WORKTREE-ISO` | Worktree Isolation（Plane A） | repository 寫入與 blast-radius 的 correctness boundary，不是 security boundary。 |
| `TERM:SANDBOX-ISO` | Sandbox Isolation（Plane B） | OS-level filesystem/network boundary；若共用 sandbox profile，並非 per-subagent 隔離。 |
| `TERM:OOB-ATTEST` | Out-of-Band Attestation | agent control plane 外的 deterministic evidence，例如 worktree write attestation 或 sandbox policy snapshot。 |
| `TERM:TIA` | Test Impact Analysis | 沿 Spec→BDD→Test traceability 選出本次值得執行的測試；只在 `GATE:GREEN` 內提升回饋速度。 |

TIA 不設 `GATE:TIA`、不取代 Red Evidence、mutation 或 `GATE:VDD`，也不允許長期把被略過的測試排除於 nightly full regression。

## 治理、證據與風險裁剪

| Stable ID | 術語 | Canonical meaning |
|---|---|---|
| `TERM:CHANGE-PROFILE` | Change Profile | `FEATURE`、`DEFECT`、`REFACTOR`、`DEPENDENCY`、`DOC_CONFIG`、`MIGRATION`、`EMERGENCY` 的 evidence applicability。 |
| `TERM:SYSTEM-PROFILE` | System Profile | web、service、mobile、data、event、IaC、AI product、internal tool 等系統型態的 assertion applicability。 |
| `TERM:WAIVER` | Time-bounded Policy Waiver | 含 scope、owner、expiry、risk、compensating control 與獨立核准的有限期例外。 |
| `TERM:BREAK-GLASS` | Break-glass Procedure | 僅於重大 incident 或營運中斷時，以最小權限、最短時間、不可變 audit 暫時繞過正常流程。 |
| `TERM:TRUST-LABEL` | Context Trust Label | 標記內容來源，例如 `TRUSTED_CANONICAL`、`TRUSTED_TOOL`、`GENERATED_UNVERIFIED`、`UNTRUSTED_USER`、`UNTRUSTED_EXTERNAL`。 |
| `TERM:EVIDENCE` | Verifiable Evidence Envelope | 將 subject、change、gate、policy、actor、tool/model、environment、hash、oracle、artifact、signature、retention 與 freshness 綁定為可驗證 evidence。 |
| `TERM:RELEASE-PROFILE` | Release Safety Profile | 定義 platform、rollout、exposure、observation、control、promotion、abort、rollback/forward-fix。 |
| `TERM:GOLDEN-TASK` | Golden Task | 版本化、可回放的 agent-workflow regression task，含 input、expected/forbidden behavior 與 oracle。 |
| `TERM:EVALOPS` | Agent EvalOps | 對 model、prompt、routing、memory、compression、tool policy 與 guardrail 做版本化、可回放的 regression evaluation。 |

## Gate taxonomy

```text
GATE:SPEC → GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY
```

| Stable ID | 位置 | 定義 |
|---|---|---|
| `GATE:ADMIT` | 上游 | Signal → deterministic admission → tiered dispatch → Change Intent；不屬五道 canonical Gate。 |
| `GATE:SPEC` | pipeline #1 | 以 Delta Spec、Impact Analysis、Stable ID、profile 與 evidence plan 決定 implementation readiness。 |
| `GATE:RED` | pipeline #2 | FEATURE／DEFECT 以 baseline failure 證明失敗能力；其他 profile 需 policy-accepted alternative evidence。 |
| `GATE:GREEN` | pipeline #3 | profile-resolved tests、static analysis、lint/type/build 與 protected-test integrity。 |
| `GATE:VDD` | pipeline #4 | 以適用的 quality evidence 檢查 validation/verification，不限於 coverage 或 mutation。 |
| `GATE:DEPLOY` | pipeline #5 | release 前的 deployability gate；Production Observation 是後續 validation，不是此 Gate 的替代。 |
| `GATE:REGRESSION` | auxiliary | agent workflow configuration 的 Golden Task regression gate；不改變 canonical pipeline。 |

## Stable ID namespaces

常用命名空間為 `TERM:`、`GATE:`、`REQ:`、`INV:`、`BDD:`、`API:`、`UI:`、`QP:`、`ADR:`、`CR:`、`SIG:`、`ADMIT:`、`WT:`、`ATTEST:` 與 `EVID:`。完整 machine-readable registry 見 [`governance/registries/namespaces.yaml`](../governance/registries/namespaces.yaml)。Stable ID 不得重用。

## 禁止混淆

1. Worktree isolation 不是 sandbox isolation，也不是 identity、data 或 supply-chain control 的替代品。
2. `not_applicable` 不是自由文字 skip；必須由 System／Change Profile 解析、提供 reason code 與替代 evidence。
3. Agent 建立 PR 不代表有 merge 權限；LLM judge 不得是高風險決策的唯一 oracle。
4. Evidence Envelope 不是自然語言自述；應指向可驗證 artifact 與其 provenance。
