# 05 · 品質屬性與 VDD 驗證（Verification & Validation）

> **Authority boundary**：此頁是 [Notion 05｜品質屬性與 VDD 驗證](https://app.notion.com/p/382f5b2d1a9081e685aefd82374b29ca) 的 repository human reference。可執行 shadow contract 位於 [`governance/gates/vdd.yaml`](../governance/gates/vdd.yaml)；衝突時以 Notion 為準。

## VDD 的定義與邊界

**VDD = Verification & Validation-Driven Development**。它在 `GATE:GREEN` 後，以 machine-checkable evidence 檢查品質屬性，並在 release 後用 Production Telemetry 驗證 operational quality assumptions。

- **Verification**：系統是否符合已核准的品質、復原與負向行為契約？
- **Validation**：在可歸因的正式環境觀測中，operational quality assumptions 是否成立？
- **不是**：Value-Driven Development、Vulnerability-Driven Development，或只看 coverage 的 CI step。

Production Telemetry 對 performance、reliability、resilience 與 user impact 是重要的實環境證據；它不能單獨證明 security、privacy、authorization 或 compliance。

## Gate position

```text
GATE:GREEN → GATE:VDD → GATE:DEPLOY → Production Observation
```

`GATE:VDD` 是固定五道 Gate 的第四道。`GATE:DEPLOY` 通過只代表具備受控發布條件；production observation 仍可能產生新的 `SIG:*`，進入下一輪 Change Intent。

## 以 profile 解析的品質證據

每次驗證前，先解析 System Profile、Change Profile、risk tier 與 assertion applicability。`not_applicable` 必須帶 policy reason code 與 alternative evidence，不能當作 skip。

| 證據類別 | 適用時的最低要求 |
|---|---|
| Failure capability | FEATURE／DEFECT 保有 Red Evidence；其他變更型別保有 policy-accepted characterization、compatibility 或替代 evidence。 |
| Test strength | profile 適用時以 mutation 或等效 evidence 檢查 assertion strength；不得只因測試全綠就跳過。 |
| Performance／reliability／resilience | 明確的 measurement location、environment、load、percentile、threshold、timeout/retry/recovery 和可重跑 artifact。 |
| Negative path | failure-path、error handling、rollback/recovery 與依 System Profile 的 edge case evidence。 |
| UI surfaces | 有 UI 時的 a11y automated evidence、必要 human review 與 visual regression。 |
| Security／privacy／authorization | 適用的 policy、design review、scan、attestation 與獨立裁決；waiver 必須有效、有限期且有補償控制。 |
| Evidence integrity | 每次結果以 Evidence Envelope 記錄 subject、change、policy、actor、tool/model、environment、hash、oracle、artifact、signature、retention 與 freshness。 |

Coverage、integration、contract 與 mutation testing 都可以是適用的 evidence，但任何固定百分比或工具選擇必須由 project quality policy 定義，不能取代 profile-resolved contract。

## VDD pass/fail semantics

`GATE:VDD` 應產出可重跑、可稽核的結果，而不是「agent 已完成」的敘述。

```text
PASS  = 所有 required assertions 有有效 evidence；任何 N/A 有 policy reason 與 alternative evidence。
FAIL  = required evidence 缺失、過期、未能重跑、違反門檻，或 waiver 無效／過期。
INCONCLUSIVE = observation window 或資料量不足；不得被當作 PASS。
```

實作 Agent 不得透過修改測試、threshold、policy、fixture 或 quarantine 使 `GATE:VDD` 看似通過。需要例外時，依 [19｜Governance Lifecycle、Waiver 與 Break-glass](19-governance-lifecycle-waiver-break-glass.md) 建立有限期、獨立核准的 `WAIVER:*`。

## Production validation

Release 後 evidence 必須能連結 release/canary attribution、observation window、control/baseline、promotion/abort/rollback decision 和目前有效的 waiver。沒有告警、成功部署或單一 SLO 達標都不是完整品質結論。

相關頁面：

- [07｜Canonical Pipeline](07-canonical-pipeline.md)
- [21｜Evidence、Provenance 與 Audit Contract](21-evidence-provenance-audit-contract.md)
- [22｜Release Safety 與 Production Verification](22-release-safety-production-verification.md)
- [24｜System／Change Profiles 與風險式裁剪](24-system-change-profiles.md)
