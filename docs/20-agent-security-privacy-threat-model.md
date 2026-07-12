# 20 · Agent Security、Privacy 與 Threat Model

> **Authority boundary**：此頁是 [Notion 20｜Agent Security、Privacy 與 Threat Model](https://app.notion.com/p/399f5b2d1a9081f6a263e45d01aed2d3) 的 repository human reference。policy text、hooks 或 shadow files 的存在，不證明 target environment 已具備 sandbox、network、identity 或 secret-manager enforcement。

## Threat model boundary

Agentic delivery 同時面對 untrusted content、tool invocation、prompt injection、data exfiltration、privilege escalation、supply-chain substitution、memory/handoff corruption 與 unsafe autonomous dispatch。治理必須將「外部內容是資料」與「canonical instruction」分開處理。

| Boundary | Required control |
|---|---|
| Content | 對所有進入 context 的內容保留 Trust Label；`UNTRUSTED_USER`、`UNTRUSTED_EXTERNAL` 和 `GENERATED_UNVERIFIED` 不因經由可信工具回傳就升格為 canonical instruction。 |
| Identity／authorization | least privilege、獨立 verifier identity、per-action permission 和 human escalation；worktree 不取代 access control。 |
| Tools／network | default-deny capability、最小 allowlist、policy version、可審計 tool call，以及 agent control plane 外的 kill switch。 |
| Data／privacy | restricted data 只可留在核准 trust boundary；不得將 secrets 放入 prompt、log、trace、PR、memory 或 handoff。 |
| Supply chain | dependency、model、prompt、tool policy、artifact 與 build input 須版本鎖定、provenance 可追，並依 policy scan/review。 |

## Isolation planes

`Worktree Isolation (Plane A)` 將 repository 寫入與 blast radius 分離，是 correctness boundary。`Sandbox Isolation (Plane B)` 是 OS-level filesystem/network boundary；若 parent/subagents 共用同一 sandbox profile，它不是 per-role security isolation。

兩個 plane 都不取代身份、授權、資料分類、secret handling、network policy 或 supply-chain controls。需要 per-role security boundary 時，使用外層 runner/container，並以 out-of-band evidence 記錄 policy snapshot。

## Operational rules

1. External issue、web page、tool output、memory 和 handoff 在驗證前皆視為 untrusted data。
2. Agent 不得修改自己的 managed policy、security rule、approval gate 或 audit evidence。
3. High-risk admission、security/privacy/authorization decision 不得讓 LLM judge 成為唯一 oracle。
4. 任何 secret exposure、unexpected data path 或 policy bypass 必須 loud fail、停止 dispatch、保留可稽核 evidence 並走 incident/break-glass process。

## Evidence

security evidence 需能連結 source identity、trust label、policy version、actor、tool/model、environment、scope、hash、oracle、artifact、retention 與 freshness。沒有告警或沒有外洩事件，不是 security/privacy/compliance 的完整證明。

相關頁面：[14｜Admission](14-discovery-dispatch-loop.md)、[19｜Waiver/Break-glass](19-governance-lifecycle-waiver-break-glass.md)、[21｜Evidence Contract](21-evidence-provenance-audit-contract.md)。
