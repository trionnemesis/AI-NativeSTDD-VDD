# 26 · Assessment Archive（dated）— 歷史評估與目前有效性

> **Status：Informative / non-normative.** 此頁是 [Notion 26｜Assessment Archive](https://app.notion.com/p/399f5b2d1a9081afbeb3d7c07cabe014) 的 repository routing summary。它管理 assessment snapshot 的生命週期與閱讀順序，不修改 glossary、registry、Gate contract 或 frozen invariant。

## Archive rule

歷史評估中的工具能力、外部數字、成熟度與建議，只在其 assessment date 和 evidence basis 下成立。每份 snapshot 都需保留日期、範圍、evidence basis、post-review note 與 `partially_superseded`／`superseded_by` 狀態；不得覆寫原始 audit history。

## Current routing

| Assessment | Current status |
|---|---|
| 08｜業界對標 | Informative dated assessment。外部產品能力、數字與法規需依 assessment date 重新查證。repository copy: [08](08-industry-comparison.md)。 |
| 16｜可建置性分層報告 | Historical buildability snapshot；是否真能 enforcement 以 12 Confirm Mode 與 21 Evidence 為準。 |
| 17｜審視報告與決策矩陣 | Partially superseded；無正式分母、權重或可重現 rubric 的比例結論不可當現況。 |
| 25｜外部對標審閱報告 | Historical review record；其建議若已納入 MCR，不代表 schema、linter、runner、oracle、CI fixture 或 conformance test 已部署。 |

## Current decision sources

現行判定依序回到 Start Here、root Canonical Glossary、02 registry、07 pipeline、12 Confirm Mode、21 evidence、24 profiles 與 18 methodology evolution。snapshot 與 canonical contract 衝突時，以 canonical authority 為準。
