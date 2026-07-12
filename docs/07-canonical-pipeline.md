# 07 · Canonical Pipeline（端到端執行流程）

> **Authority boundary**：此頁是 [Notion 07｜端到端執行流程與落地清單](https://app.notion.com/p/382f5b2d1a9081ea8de4d42a6f8bdabc) 的 repository human reference。Notion 07 是唯一 canonical 12-step／5-Gate 序列；repository 的 [`governance/gates/`](../governance/gates/) 僅是 non-authoritative shadow。

## 固定序列

```text
GATE:SPEC → GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY
```

五道 Gate 的順序與數量不可由 agent 改寫。`GATE:ADMIT` 是上游 admission control；`GATE:REGRESSION` 是 agent-workflow configuration 的 auxiliary gate；兩者都不是第六道 pipeline Gate。

## Canonical 12 steps

```text
1. Change Intent
2. Delta Spec
3. Impact Analysis
4. GATE:SPEC
5. Independent Test Generation
6. GATE:RED
7. AI Implementation
8. GATE:GREEN
9. GATE:VDD
10. Traceability Generation
11. Controlled Deployment
12. Production Verification → Change Intent / Accepted Evidence
```

每個 Gate 執行前先解析 `System Profile + Change Profile + risk tier + policy version`。任何 `not_applicable` assertion 都必須由 profile policy 決定、保留 reason code 與 alternative evidence；高風險 assertion 不能由 implementation agent 自行標記為 N/A。

## Gate contracts

| Gate | 進入條件與必須 evidence | 拒絕條件 |
|---|---|---|
| `GATE:SPEC` | Change Intent、Delta Spec、Impact Analysis、Stable ID、profile resolution、適用的 domain/BDD/UI/API/quality/release contract，以及 evidence plan。 | 規格不完整、相容性未分類、profile applicability 未解決，或 evidence plan 缺失。 |
| `GATE:RED` | FEATURE／DEFECT 的 baseline failure + requirement-matching oracle；REFACTOR、DEPENDENCY、DOC_CONFIG、MIGRATION、EMERGENCY 的 policy-accepted alternative evidence。 | 測試無失敗能力、failure 不對應 requirement、整個 SUT 被 mock，或 test actor 可讀新 implementation solution。 |
| `GATE:GREEN` | profile-resolved tests、static analysis、lint/type/build、flaky/quarantine policy、protected-test integrity，以及啟用 TIA 時的 selection/fallback evidence。 | 任何 required suite 失敗、選測削弱 nightly full regression，或 implementation agent 弱化測試／threshold／policy／fixture。 |
| `GATE:VDD` | profile 適用的 mutation、performance、reliability、resilience、negative path、a11y/visual 與 security/privacy/authorization evidence。 | required quality evidence 缺失、過期或無法重跑；waiver 無效或已過期。 |
| `GATE:DEPLOY` | Release Profile、migration compatibility、controlled rollout、observation window、promotion/abort/rollback、smoke test、SBOM/provenance/signature、dashboard/alert/runbook。 | release 不可安全控制、無可執行 rollback/forward-fix，或 observation/operational evidence 無法歸因。 |

`GATE:DEPLOY` 是**發布前**的 deployability gate。正式環境的 Production Verification 是下一層 operational validation：資料不足時結論為 `INCONCLUSIVE`，不是 PASS；security、privacy、authorization、compliance 也不能只靠「未告警」證明。

## Upstream admission 與 auxiliary evaluation

```text
Signal → fingerprint → deterministic dedup → LLM-assisted classification
       → GATE:ADMIT → tiered dispatch (role × worktree × budget)
       → Change Intent → canonical pipeline
```

- `GATE:ADMIT` 保留來源身份、trust label、provenance、queue budget、tier decision 與 dispatch assignment；LLM 不得是唯一 admission authority。
- Test Impact Analysis（TIA）只在 `GATE:GREEN` 選擇本次測試集合；它不改寫 Gate，也不設 `GATE:TIA`。
- `GATE:REGRESSION` 以 Golden Tasks 和可重放 evidence 檢查 prompt、model、memory、routing、tool policy、guardrail 的組態變更；它的被測物不是產品功能。

## 最小 Traceability

```text
SIG:* → ADMIT:* → autonomy tier / dispatch / WT:* attestation
      → System Profile + Change Profile + policy version
      → REQ / INV / BDD / UI / API contract
      → red-or-alternative EVID:* → test / quality evidence
      → release / canary attribution → production observation
      → Evidence Envelope index
```

Evidence Envelope 必須能連結 policy、actor、tool/model、environment、hash、oracle、artifact、signature、retention 與 freshness。Notion 摘要或 agent 自述不是完整 evidence。

## 導入順序

1. Stable ID、System／Change Profile 與 Requirement-Test traceability。
2. Delta Spec、Impact Analysis、compatibility/migration classification。
3. Evidence Envelope、Red／alternative evidence、protected-test guard。
4. changed-code mutation、flaky/hermetic policy、Critical Journey Quality Profile。
5. Release Profile、controlled rollout、observation、rollback 與 supply-chain provenance。
6. Production Signal、upstream admission 與受控回饋。

相關 machine contracts：[`governance/gates/`](../governance/gates/)、[`governance/profiles/`](../governance/profiles/)、[`governance/examples/`](../governance/examples/)。它們在 shadow mode 只提供 comparison material，不證明 target environment 已 enforcement。
