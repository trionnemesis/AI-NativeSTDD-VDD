# 18 · 方法論演進協定（Methodology Evolution Protocol）

> **Authority boundary**：此頁是 [Notion 18｜方法論演進協定](https://app.notion.com/p/394f5b2d1a9081b0b30beb6883b74017) 的 repository human reference。它管理方法論演進與 audit，不新增或重排 canonical Gate。

## 目的

方法論必須可跨模型、跨 agent、跨時間接力，同時避免因一次同步、prompt 更新或工具升級而悄悄改寫核心治理語意。每個提案先以 delta 說明，再經可追溯的人類裁決。

## Agent onboarding order

在提出方法論變更前，agent 必須依序：

1. 讀取 Start Here、root Canonical Glossary、07 pipeline、24 profiles 與本頁。
2. 確認 authority state、適用 Change Profile、risk tier 與既有 stable IDs。
3. 提出 delta-first rationale、受影響 contract、failure-case analogue、evidence、migration/rollback 與 observation plan。
4. 將不確定性、policy conflict 和人類決策需求明確標示，不得自行完成 authority cutover。

## Frozen invariants

agents 不得自行變更：

- 六項治理原則。
- `GATE:SPEC → RED → GREEN → VDD → DEPLOY` 的五道固定序列。
- 已存在 Stable ID 的語意或重用既有 ID。
- append-only methodology ledger 的歷史。
- D-T3／高風險 control relaxation 的人類決策權。

新頁從 27 起新增，不重新編號既有頁面。評估、工具比較與其他 historical material 以版本化 archive 保存，不覆寫原始 evidence basis。

## MCR lifecycle

Methodology Change Request（MCR）至少包含：scope、rationale、受影響 authority、delta、invariant check、evidence、risk、migration、rollback、owner、human decision 與 observation。任何 control relaxation 都需要 human D-T3 MCR，不得以 agent 自評取代。

`MCR:2026:004` 建立了本 repository 的 `governance/` shadow 與 generated view；它沒有完成 authority cutover。仍待 Notion semantic comparison、rollback dry run、observation window 與 explicit human approval，詳見 [`governance/manifest.yaml`](../governance/manifest.yaml)。

## Audit rule

Notion 仍是 canonical。repository shadow、schema validation 或 generated view 的存在，僅代表可比較的 artifact；遇衝突必須 loud fail，不能靜默選擇 repository。

相關頁面：[19｜Governance Lifecycle](19-governance-lifecycle-waiver-break-glass.md)、[21｜Evidence Contract](21-evidence-provenance-audit-contract.md)、[26｜Assessment Archive](26-assessment-archive.md)。
