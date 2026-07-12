# 14 · Discovery & Dispatch Loop（upstream `GATE:ADMIT`）

> **Authority boundary**：此頁是 [Notion 14｜Discovery & Dispatch Loop](https://app.notion.com/p/388f5b2d1a9081789657dbfc101ca8e6) 的 repository human reference。`GATE:ADMIT` 位於 07 canonical pipeline 的上游；它不改變 12 steps 或五道 Gate 的固定順序。

## 目的與邊界

Discovery & Dispatch 將雜訊 signal 收斂為可處理的 Change Intent：

```text
Signal → fingerprint → deterministic dedup → LLM-assisted classification
       → GATE:ADMIT → tiered dispatch (role × WT:* × budget)
       → Change Intent → 07 step 1
```

它回答「這個 signal 是否足以形成 Change Intent、誰可以處理、可自動到什麼程度」，**不**決定產品商業優先級。queue order 必須引用外部 `priority_reference`；LLM 不得自行推斷商業價值。

TIA 不屬本頁：它在 dispatch 後、`GATE:GREEN` 內回答「哪些測試值得跑」，不是 admission gate 或品質唯一權威。

## Source、trust 與 admission constraints

| 必要控制 | 說明 |
|---|---|
| Source authenticity | 保存 service/requester identity、signature/token validation、event ID、payload hash、received time 與 ruleset/query version。 |
| Trust label | CI、scanner、telemetry、issue 與 external content 都依 [20｜Agent Security](20-agent-security-privacy-threat-model.md) 標記 trust；`UNTRUSTED_EXTERNAL` 不可直接觸發高權限 dispatch。 |
| Deterministic dedup | 每個 signal 必有 fingerprint；dedup 由 deterministic ruleset 決定，不能由 LLM 唯一裁決。 |
| Bounded queue | 依 source/service 設 rate limit、pending/concurrent/tokens/time/cost budget、backpressure、cancellation 與 supersession。 |
| Test-path reroute | 觸及 test path 的 signal 改道至 Self-Healing CI governance，禁止直接當一般 implementation dispatch。 |
| Provenance | 從 `SIG:*` 到 `ADMIT:*`、tier、dispatch、worktree attestation 的關係需寫入 Evidence Envelope。 |

高嚴重度 classification 必須有 deterministic corroboration，例如 CVE exact match、SLO numeric breach 或 baseline test-red。LLM 可以提供 `type`、`severity`、`affected_ids` 作為資料，但不能成為唯一 authority。

## `GATE:ADMIT` outcome

| Outcome | 說明 |
|---|---|
| `ADMIT` | source、trust、provenance、dedup、queue、tier、severity corroboration、Definition of Ready 均符合；輸出 Change Intent。 |
| `REJECT` | untrusted source、無 provenance 或 duplicate。 |
| `DEFER` | backpressure、未滿 Definition of Ready 或需要 untrusted-content review。 |
| `ESCALATE` | T3、未佐證的 high severity 或其他需人類裁決的情況。 |
| `REROUTE` | test-path / self-healing 類 signal 改走受控維運迴圈。 |

每種非 ADMIT 結果都必須 loud fail，不能靜默 dispatch。

## Autonomy tiers

| Tier | Deterministic boundary | 允許動作 |
|---|---|---|
| **T1** | low-severity `dependency_patch`、`lint`、`doc_drift`。 | auto-dispatch + draft/propose PR；worktree write attestation 先 PASS，direct merge 受 managed policy 限制。 |
| **T2** | bug 或 performance regression 且不觸及 invariant；未命中其他規則時的 default。 | auto-dispatch + draft PR + mandatory human review。 |
| **T3** | touches invariant、security、schema migration，或 uncorroborated high severity。 | human-written Change Intent；禁止 auto-dispatch。 |

Tier mapping 是 deterministic、可稽核規則。T1 仍需依風險抽樣 review；misclassification、revert、incident、scope escape 或 human amendment 超過 policy threshold 時，規則必須收緊至 T2，而不是由模型自行放寬。

## Dispatch and isolation

`ADMIT(tier)` 後才配置 `WT:*` worktree、agent role 和 time/token budget。Worktree isolation 是 repository correctness boundary；sandbox isolation 是 process-level filesystem/network boundary。兩者皆不等於 identity、authorization、data classification 或 supply-chain control。

role-conditional test/implementation separation、worktree write attestation 與 sandbox policy snapshot 應在 agent control plane 之外產生可驗證 evidence。現有 repository shadow 描述目標 contract，並不宣稱所有 target project 已具備 per-role container isolation。

## 與 `GATE:SPEC` 的交界

| `GATE:ADMIT` | `GATE:SPEC` |
|---|---|
| 輸入是 signal 與 raw context；輸出是 Change Intent、provisional profile、tier 和 dispatch provenance。 | 輸入是 Change Intent；輸出是已核准的 Delta Spec、Impact Analysis、Stable IDs、applicability 和 evidence plan。 |
| 決定可否建立/派發變更工作。 | 決定變更是否已可進入 independent test generation 與 implementation。 |

相關 contract：[`governance/gates/admit.yaml`](../governance/gates/admit.yaml)、[07｜Canonical Pipeline](07-canonical-pipeline.md)、[13｜Self-Healing CI](13-self-healing-ci.md)。
