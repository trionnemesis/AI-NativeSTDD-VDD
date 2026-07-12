# 15 · Test Impact Analysis（`GATE:GREEN` 內的選測效率層）

> **Authority boundary**：此頁是 [Notion 15｜Test Impact Analysis](https://app.notion.com/p/38ff5b2d1a9081cc95b6c1baec065698) 的 repository human reference。TIA 的 machine-readable terminology 可見 [`governance/glossary.yaml`](../governance/glossary.yaml)；它不新增 Gate。

## 定義與固定邊界

Test Impact Analysis（TIA）沿著 `Spec → BDD → Test` 的 Stable ID traceability，挑出一次變更後值得在目前 CI 迴圈執行的 `selected tests`，縮短 `GATE:GREEN` 的回饋時間。

```text
changed scope + traceability + admission provenance
    → selected tests + always-run suites + fallback
    → GATE:GREEN evidence
```

- TIA 是 delivery-efficiency layer，不是 testing methodology、quality oracle、admission control 或 self-healing。
- 不存在 `GATE:TIA`；canonical pipeline 仍是 `SPEC → RED → GREEN → VDD → DEPLOY`。
- TIA 只選擇既有測試，不能改 assertion、locator、fixture、quarantine 或測試內容。

## 不可削弱的 controls

TIA 不得削減以下要求：

1. `GATE:RED` 的 failure capability、implementation/test actor separation 與 Red Evidence。
2. protected-test integrity、mutation 或 `GATE:VDD` 的 applicable quality evidence。
3. always-run suites 與 nightly full regression；長期排除有失敗能力的測試是 reject 條件。
4. profile-required security、privacy、authorization、release 或 recovery evidence。

## 選測輸入與決策

| Input | 最低要求 |
|---|---|
| Change scope | 來自 worktree changed files/functions、Change Intent、Impact Analysis 與 admission provenance。 |
| Traceability | `REQ/INV → BDD/UI/API → tests` 的 Stable ID mapping 與版本。 |
| Policy | selected tests、always-run suites、fallback mode、nightly owner、freshness threshold。 |
| Evidence | selection result、mapping version、reason、test run、miss/recall/freshness metrics 與 Evidence Envelope。 |

未知、過期、動態或不完整的 mapping 不可假裝精準：回退 full regression，或升級人工裁決。

## 成功判定

TIA 的成功是更快取得同等或更明確的 `GATE:GREEN` evidence，不是提高 correctness 分數。應監控 selection recall、miss rate、mapping freshness、fallback rate、selected-test latency 和 nightly full-regression health；若未達 policy SLO，收緊選測或停用 TIA，而不是降低品質門檻。

相關頁面：[07｜Canonical Pipeline](07-canonical-pipeline.md)、[06｜防偽測試](06-anti-fake-test.md)、[23｜Agent EvalOps](23-agent-evalops-configuration-regression.md)。
