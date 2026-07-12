# 19 · Governance Lifecycle、Waiver 與 Break-glass

> **Authority boundary**：此頁是 [Notion 19｜Governance Lifecycle、Waiver 與 Break-glass](https://app.notion.com/p/399f5b2d1a9081148c2cd1b283e80f16) 的 repository human reference。範例 [`governance/examples/waiver.yaml`](../governance/examples/waiver.yaml) 只是 schema-aligned example，不是 runtime enforcement 證明。

## Policy lifecycle

每個 machine policy 至少要能識別其 ID、version、owner、effective date、review cycle、enforcement point 與 required evidence。變更 policy 時，必須能追溯其 rationale、受影響 Gate/profile、migration、rollback 與人類裁決。

| State | 必要條件 |
|---|---|
| Draft | 有 owner、scope、policy version 與可驗證的 proposal evidence。 |
| Active | enforcement/evidence contract 已定義，且適用者可查。 |
| Superseded | 指向取代規則，保留歷史與生效區間。 |
| Retired | 不可刪除 audit trail；保留 tombstone 與退役理由。 |

## Waiver

Waiver 是**有限期的風險接受**，不是永久 gate skip。有效 `WAIVER:*` 必須含：

- 明確 scope、affected subject、owner、expiry、risk statement、compensating controls 與獨立核准。
- 可驗證的 evidence、policy version、revalidation／expiry handling 和 audit record。
- 不得取消 authentication、authorization、audit integrity、data-protection basics、secrets/least-privilege 或其他 always-on controls。

過期、範圍不明、由 implementation agent 自核，或缺少補償控制的 waiver 一律無效。

## Break-glass

Break-glass 只適用重大 incident、material outage 或受法規時限約束的緊急情況。它必須以最小權限、最短時間運作，並要求：

1. named human authority、明確的 incident/reason、scope 和 expiry。
2. immutable audit、即時 revocation／自動到期、受控 access 與 evidence capture。
3. 24 小時內 preliminary review，以及五天內補齊 evidence、remediation Change Intent 與 retrospective。

Break-glass 不是 daily fast path，也不能用來規避正常 review、Release Profile 或 Evidence Envelope。

## Control relaxation

降低 Gate、policy 或 autonomy control 的嚴格度是 human D-T3 change：需要 MCR、risk assessment、alternative controls、migration、rollback、observation 和 explicit approval。Agent 不得因成本、速度或單次成功自行放寬規則。

相關頁面：[21｜Evidence Contract](21-evidence-provenance-audit-contract.md)、[22｜Release Safety](22-release-safety-production-verification.md)、[24｜Profiles](24-system-change-profiles.md)。
