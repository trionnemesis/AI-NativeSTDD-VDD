# 23 · Agent EvalOps 與組態回歸治理

> **Authority boundary**：此頁是 [Notion 23｜Agent EvalOps 與組態回歸治理](https://app.notion.com/p/399f5b2d1a9081659027ec1b296d10be) 的 repository human reference。machine shadow 參見 [`governance/gates/regression.yaml`](../governance/gates/regression.yaml) 與 [`governance/examples/golden-task.yaml`](../governance/examples/golden-task.yaml)。

## 被測物與邊界

Agent EvalOps 的被測物是**agent-workflow configuration**，例如 model、prompt、routing、memory/compression strategy、tool policy、guardrail、environment、budget 和 seed；它不是產品功能測試，也不是一次性的 benchmark。

`GATE:REGRESSION` 是 auxiliary gate，不屬 `GATE:SPEC → RED → GREEN → VDD → DEPLOY`。其目的在於阻止 agent configuration 變更造成 safety、correctness、cost 或 latency regression。

## Golden Tasks

Golden Task 是版本化、可回放的 evaluation artifact，至少描述：

- input/context、preconditions、expected behavior、forbidden behavior、risk/data classification。
- deterministic 或獨立 oracle、assertion、scoring、failure semantics 與 required Evidence Envelope。
- baseline、policy version、model/prompt/tools/memory/routing/environment/budget/seed versions。

LLM-as-judge 可以提供輔助訊號，但不能作為 high-risk outcome 的唯一 oracle；deterministic 或 independent oracle 優先。

## `GATE:REGRESSION` criteria

```text
pass_rate >= baseline - tolerance
cost and latency <= budget
no critical safety/correctness failures
schema/provenance complete and replayable
variance within policy
```

任何 critical failure、不可重放 evidence、缺少版本資訊、或以單一 pass rate 遮蔽 cost/latency regression，都應 fail/defer。agent 不得自行降低 baseline、tolerance 或 quality threshold。

## Rollout

組態變更以 `shadow → limited cohort → broader rollout` 漸進；每一步保留 decision、evidence、owner、rollback trigger 與 observation result。新 model、prompt 或 tool policy 上線後，T1 tier mapping 應先提高抽樣 review，通過 regression 與 observation 才能降低。

相關頁面：[15｜TIA](15-test-impact-analysis.md)、[18｜Methodology Evolution](18-methodology-evolution-protocol.md)、[21｜Evidence Contract](21-evidence-provenance-audit-contract.md)。
