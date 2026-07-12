# 24 · System／Change Profiles 與風險式裁剪

> **Authority boundary**：此頁是 [Notion 24｜System／Change Profiles 與風險式裁剪](https://app.notion.com/p/399f5b2d1a90813ea4bdc269771615f7) 的 repository human reference。machine shadow 位於 [`governance/profiles/`](../governance/profiles/)；Notion 仍是 canonical authority。

## 目的

五道 Gate 的順序固定，但每個 assertion 的適用性依 System Profile、Change Profile、risk tier、risk flags、policy version 和核准 override 解析。衝突時採較嚴格規則。

```yaml
profile_resolution:
  system_profile: "TERM:SYSTEM-PROFILE instance"
  change_profile: "FEATURE | DEFECT | REFACTOR | DEPENDENCY | DOC_CONFIG | MIGRATION | EMERGENCY"
  risk_tier: "T1 | T2 | T3"
  policy_version: "version"
  assertion:
    status: "required | not_applicable"
    reason_code: "policy enum"
    alternative_evidence_ids: ["EVID:*"]
```

`not_applicable` 不等於 skip。它必須由 policy resolver 產生、包含 reason code 和 alternative evidence；implementation agent 不能自己把 high-risk control 標記 N/A。

## System Profiles

| System profile | 典型額外 assertion |
|---|---|
| `WEB_FRONTEND` | UI state、a11y、visual/interaction、browser matrix、RUM、feature flag。 |
| `BACKEND_SERVICE_API` | API/event compatibility、SLO、load、authorization、resilience、canary、consumer impact。 |
| `MOBILE` | device/OS matrix、offline、permissions、signing、store rollout、remote kill、non-immediate rollback。 |
| `DATA_PIPELINE` | schema、lineage、data quality、replay、idempotency、backfill、privacy、late/duplicate data。 |
| `EVENT_DRIVEN` | event schema、ordering、dedup、consumer compatibility、DLQ、replay、eventual consistency。 |
| `INFRASTRUCTURE_IAC` | plan、policy-as-code、drift、blast radius、state protection、credential、rollback/recreate。 |
| `AI_LLM_PRODUCT` | dataset/prompt/model version、safety eval、tool policy、trace、human escalation、cost、latency。 |
| `INTERNAL_TOOL` | authentication、authorization、audit、data classification。 |

## Change Profiles

| Change profile | Core evidence |
|---|---|
| `FEATURE` | full spec、Red Evidence、GREEN、applicable VDD、controlled release。 |
| `DEFECT` | reproducer/regression、failure path、affected quality verification。 |
| `REFACTOR` | characterization or regression evidence、API compatibility、mutation or equivalent evidence。 |
| `DEPENDENCY` | SCA、SBOM、license、API/ABI compatibility、regression、supply-chain provenance。 |
| `DOC_CONFIG` | spec-lite、green-lite 與 profile-resolved alternative evidence；不代表零 evidence。 |
| `MIGRATION` | expand/contract、backfill、compatibility、rollback or forward-fix。 |
| `EMERGENCY` | post-event evidence、review、remediation Change Intent；必要時受 break-glass 管理。 |

## Always-on controls

下列 controls 不得以 risk tailoring 或 N/A 取消：identity/provenance、protected controls、secrets/least privilege、audit integrity、authorization/permissions、data-protection basics，以及 named human exception approval。任何 waiver 仍須是有限期、可驗證、獨立核准的例外。

## Gate integration

`GATE:SPEC` 必須留下 profile manifest/resolution；後續 Gate 用同一 profile version 解析 required tests、quality、release 與 evidence。Profile policy 變更依 [18｜Methodology Evolution](18-methodology-evolution-protocol.md) 和 [19｜Governance Lifecycle](19-governance-lifecycle-waiver-break-glass.md) 管理。

相關檔案：[`governance/profiles/system.yaml`](../governance/profiles/system.yaml)、[`change.yaml`](../governance/profiles/change.yaml)、[`applicability.yaml`](../governance/profiles/applicability.yaml)。
