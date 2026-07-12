# 22 · Release Safety 與 Production Verification

> **Authority boundary**：此頁是 [Notion 22｜Release Safety 與 Production Verification](https://app.notion.com/p/399f5b2d1a9081638f16d71b6ca3dfab) 的 repository human reference。machine shadow 參見 [`governance/gates/deploy.yaml`](../governance/gates/deploy.yaml) 與 [`governance/examples/release-profile.yaml`](../governance/examples/release-profile.yaml)。

## `GATE:DEPLOY` 的語意

`GATE:DEPLOY` 代表**具備安全發布條件**，不是 production quality 已被確認。它位於 `GATE:VDD` 後、受控 release 前；發布後的 observation 依 evidence 決定 promotion、abort、rollback/forward-fix 或產生新的 Signal。

```text
GATE:VDD → deploy-ready → controlled rollout → observation
         → promote | abort | rollback/forward-fix | new SIG:*
```

## Release Profile

每次 release 以可版本化的 Release Profile 定義：

| Field | Purpose |
|---|---|
| platform / system profile | 適用 rollout、compatibility 與 safety assertion。 |
| rollout / exposure | feature flag、canary、cohort、region、control/baseline 與 attribution。 |
| observation | SLI/SLO、measurement window、owner、data sufficiency 與 dashboard/alert。 |
| decision criteria | promotion、abort、rollback/forward-fix 的 deterministic threshold。 |
| recovery | migration compatibility、rollback/recreate、runbook、smoke test 與 escalation path。 |
| provenance | SBOM、build provenance、artifact signature、policy version、active waiver。 |

Observation window 至少應涵蓋相應 SLI 的計算週期；資料不足、無法歸因或控制組缺失時結論是 `INCONCLUSIVE`。成功 deploy、沒有 alert 或單一 SLO 綠燈，都不是完整 production verification。

## System-specific constraints

- Migration：須可 reverse 或採 expand/contract、backward compatibility、backfill/replay、forward-fix control。
- Mobile：考量 signing、store rollout、remote kill 與不可即時回滾。
- Data/event systems：考量 schema compatibility、ordering、dedup、DLQ、replay、late/duplicate data。
- Security/privacy/authorization/compliance：仍需多源 evidence 與獨立裁決；production telemetry 不能是唯一 proof。

## Evidence and lifecycle

Release decision 必須可追溯到 Release Profile、`GATE:VDD` evidence、controlled rollout config、smoke test、rollback runbook、artifact provenance、waiver record 與 production observation。所有 state transition 用 Evidence Envelope 記錄，不讓 agent 以自然語言宣稱發布安全。

相關頁面：[05｜VDD](05-vdd-verification.md)、[07｜Canonical Pipeline](07-canonical-pipeline.md)、[21｜Evidence Contract](21-evidence-provenance-audit-contract.md)。
