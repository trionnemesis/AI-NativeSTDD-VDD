# Generated Canonical View — STDD × VDD

> **GENERATED FILE — DO NOT EDIT.** Source: `governance/**/*.yaml`.
> Authority: **NOTION_CANONICAL**; repository state: **SHADOW_NON_AUTHORITATIVE**.
> Source snapshot: 2026-07-11 · MCR: `MCR:2026:004` · bundle SHA-256: `99b9e38f485ebba01b77a7e4b1549efb9a0cf781c4f7f81ea1162b84823f22c0`.

## Five-gate canonical pipeline

`GATE:SPEC` → `GATE:RED` → `GATE:GREEN` → `GATE:VDD` → `GATE:DEPLOY`

`GATE:ADMIT` is upstream. `GATE:REGRESSION` is auxiliary. Neither is a sixth pipeline gate.

| Gate | Stage | Contract |
|---|---|---|
| `GATE:SPEC` | spec_approval | 07 GATE:SPEC |
| `GATE:RED` | red | 07 GATE:RED + 06 Red Evidence |
| `GATE:GREEN` | green | 07 GATE:GREEN |
| `GATE:VDD` | quality_v_and_v | 05 GATE:VDD + 07 Gate 4 |
| `GATE:DEPLOY` | deploy | 07 GATE:DEPLOY |

## Canonical glossary

| Stable ID | Canonical term | Operational meaning |
|---|---|---|
| `TERM:STDD` | Specification & Test-Driven Development | 以 Canonical Spec + Test 作為硬約束,限制 AI 實作範圍; 實作不得超出 spec 與測試界定的行為集合。 |
| `TERM:VDD` | Verification & Validation-Driven Development | 功能通過驗收(Green)後,於 pre-Deploy 對品質屬性 (performance / reliability / security / resilience) 執行 machine-checkable gate；部署後以 Production Telemetry 對 operational quality assumptions 做最終實環境驗證。 可執行 gate 規格: GATE:VDD(見 05 頁)。 |
| `TERM:DDD` | Domain-Driven Design | 定義業務邊界、ubiquitous language 與不變條件 invariants。 |
| `TERM:BDD` | Behavior-Driven Development | 以 Given-When-Then 定義使用者可觀察行為與驗收情境。 |
| `TERM:DI` | Dependency Injection | 讓依賴可替換、元件可隔離、測試可成立。 |
| `TERM:UI-STATE` | UI State Contract | 補足 Loading／Error／Empty／Disabled 等互動狀態契約。 |
| `TERM:SIGNAL` | Discovery Signal | 來自 CI／Production Telemetry／SCA·CVE／dependency／drift／人工 issue 的原始事件; 必含 fingerprint。為 Change Intent 的 upstream 觸發源,實例命名空間 SIG:(見 14)。 |
| `TERM:ADMISSION` | Admission Control | 把 triaged signal 升級為 Change Intent 前的 deterministic 准入裁決; 可執行契約 GATE:ADMIT(見 14)。LLM 不得為唯一裁決者。 |
| `TERM:AUTONOMY-TIER` | Autonomy Tier | 任務可自動化程度的 deterministic 分級。T1=auto-PR;T2=auto-PR+強制 human review; T3=須人工撰寫 Change Intent、禁止 auto-dispatch。映射與 enforcement 見 14。 |
| `TERM:DISPATCH` | Dispatch Assignment | subagent role x worktree(WT:) x budget(time／token cap) 的派工綁定。 |
| `TERM:WORKTREE-ISO` | Worktree Isolation (Plane A) | repo 內寫入邊界。Claude Code agents view 對每個 subagent 配獨立 git worktree + worktree-isolation guard。屬 correctness／blast-radius 邊界,非安全邊界。 |
| `TERM:SANDBOX-ISO` | Sandbox Isolation (Plane B) | OS 級 FS／network 邊界(bubblewrap／seatbelt)。process 級、非 per-subagent: subagent 與 parent 共用同一 sandbox profile。per-role 安全切分需外層 runner／container。 |
| `TERM:OOB-ATTEST` | Out-of-Band Attestation | 在 agent 控制平面之外執行的 deterministic 檢查,產生不可由 agent 自證偽造的證據; 用於 worktree 寫入驗證與 sandbox policy 快照。為 GATE:VDD machine-checkable 哲學的延伸。 |
| `TERM:TIA` | Test Impact Analysis | 一次變更後,沿 Spec->BDD->Test 的 Stable ID traceability, 挑出受影響、值得在本次 CI 迴圈執行的測試子集(selected tests),縮短 GATE:GREEN 回饋時間。 屬交付效率層,落在 GATE:GREEN 內部;非獨立 Gate、不改 07 canonical 序列。 被略過測試由 nightly Full Regression 兜底。成熟度位階=L4(加速驗證),先於 13 Self-Healing 之 L5。主定義頁見 15。 |
| `TERM:GOLDEN-TASK` | Golden Task | 版本化的 agent workflow 評測任務(輸入 + 預期行為 + oracle 綁定), 用於 prompt／routing／memory strategy／tool policy／model 換版後的可重複 regression 評測。 artifact(golden_tasks.jsonl + replay script)落於 repo;Notion 僅存契約與 schema(見 18)。 |
| `GATE:REGRESSION` | Agent Regression Gate | agent 組態變更(prompt／model／memory／tool policy)的 machine-checkable 准入條件: golden task pass_rate >= baseline - tolerance 且 cost／latency <= budget。 為 18 方法論演進協定「新模型讀懂判定」的可執行證據形式; 哲學沿用 GATE:VDD(machine-checkable)與原則 5(可證明失敗能力)。 |
| `TERM:CHANGE-PROFILE` | Change Profile | 依 FEATURE／DEFECT／REFACTOR／DEPENDENCY／DOC_CONFIG／MIGRATION／EMERGENCY 判定既有 Gate assertion 的適用性與所需 evidence；權威頁見 24。 |
| `TERM:SYSTEM-PROFILE` | System Profile | 依 web／service／mobile／data／event／IaC／AI product 等系統型態， 決定 UI、API、quality、release 與安全 assertion 的適用範圍；權威頁見 24。 |
| `TERM:WAIVER` | Time-bounded Policy Waiver | 具 scope、owner、期限、風險聲明、補償控制與獨立核准的有限期例外；權威頁見 19。 |
| `TERM:BREAK-GLASS` | Break-glass Procedure | 僅於重大事故或營運中斷時，以最小權限、最短時間與不可變稽核暫時繞過正常流程；權威頁見 19。 |
| `TERM:TRUST-LABEL` | Context Trust Label | 標記進入 Agent context 的內容來源信任層級，如 TRUSTED_CANONICAL、 TRUSTED_TOOL、GENERATED_UNVERIFIED、UNTRUSTED_USER、UNTRUSTED_EXTERNAL；權威頁見 20。 |
| `TERM:EVIDENCE` | Verifiable Evidence Envelope | 綁定 subject、change、Gate、policy version、actor、tool／model、environment、hash、oracle、 artifact、signature、retention 與 freshness 的可驗證證據；權威頁見 21。 |
| `TERM:RELEASE-PROFILE` | Release Safety Profile | 定義 platform、rollout strategy、exposure、observation window、control、promotion、abort、rollback／forward-fix；權威頁見 22。 |
| `TERM:EVALOPS` | Agent EvalOps | 對 model／prompt／routing／memory／compression／tool policy／guardrail 的版本化、可回放回歸評測；權威頁見 23。 |

## System profiles

| Profile | Concerns |
|---|---|
| `WEB_FRONTEND` | ui_state, accessibility, visual_interaction, browser_matrix, rum, feature_flag |
| `BACKEND_SERVICE_API` | api_event_compatibility, slo, load, authorization, resilience, canary, consumer_impact |
| `MOBILE` | device_os_matrix, offline, permissions, signing, store_rollout, remote_kill, non_immediate_rollback |
| `DATA_PIPELINE` | schema, lineage, data_quality, replay, idempotency, backfill, privacy, late_duplicate_data |
| `EVENT_DRIVEN` | event_schema, ordering, deduplication, consumer_compatibility, dlq, replay, eventual_consistency |
| `INFRASTRUCTURE_IAC` | plan, policy_as_code, drift, blast_radius, state_protection, credential, rollback_or_recreate |
| `AI_LLM_PRODUCT` | dataset_version, prompt_version, model_version, safety_eval, tool_policy, trace, human_escalation, cost, latency |
| `INTERNAL_TOOL` | authentication, authorization, audit, data_classification |

## Change profiles

| Profile | Red evidence | Requirements |
|---|---|---|
| `FEATURE` | required | full_spec, green, applicable_vdd, controlled_release |
| `DEFECT` | required_reproducer | regression, failure_path, affected_quality_verification |
| `REFACTOR` | alternative_allowed | characterization_or_regression, api_compatibility, mutation_or_equivalent_evidence |
| `DEPENDENCY` | alternative_allowed | sca, sbom, license, api_abi_compatibility, regression, supply_chain_provenance |
| `DOC_CONFIG` | alternative_allowed | spec_lite, green_lite |
| `MIGRATION` | alternative_allowed | expand_contract, backfill, compatibility, rollback_or_forward_fix |
| `EMERGENCY` | alternative_allowed | post_event_evidence, review, remediation_change_intent |

## Authority boundary

This generated view is non-authoritative during shadow mode. Conflicts must fail loudly and be resolved against the Notion source until explicit cutover approval.
