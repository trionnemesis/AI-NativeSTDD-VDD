# AI-Native STDD × VDD 工程治理系統

[![Governance shadow validation](https://github.com/trionnemesis/AI-NativeSTDD-VDD/actions/workflows/governance-shadow.yml/badge.svg)](https://github.com/trionnemesis/AI-NativeSTDD-VDD/actions/workflows/governance-shadow.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](requirements-governance.txt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 讓 agentic development 對專業人士可信的 verification architecture。

This repository provides Claude Code-ready governance templates, a Codex/Hermes adapter, and a machine-readable shadow of an AI-native **Specification & Test-Driven Development / Verification & Validation-Driven Development** methodology.

It addresses three recurring failure modes:

1. Spec drift across requirements, BDD, UI, API, tests, and quality contracts.
2. Fake-green or self-certifying tests produced or weakened by the implementation Agent.
3. Uncontrolled automated repair or delivery that hides regression, security, or operational risk.

## 36 秒看懂

[![AI-Native STDD × VDD 投影片式專案介紹](docs/media/ai-native-stdd-vdd-intro.gif)](docs/media/ai-native-stdd-vdd-intro.mp4)

## 從這裡開始

- **人類讀者**：[AI-Native STDD × VDD｜人類閱讀版](https://app.notion.com/p/3a2f5b2d1a9081f7a93ff2af3a6933a9)
- **歷史／稽核／回復**：[Archive｜舊版技術、Agent 與治理文件](https://app.notion.com/p/399f5b2d1a9081afbeb3d7c07cabe014)
- **Agent**：先讀 [`governance/manifest.yaml`](governance/manifest.yaml)，再依 [`setup/AGENT_SETUP_PROTOCOL.md`](setup/AGENT_SETUP_PROTOCOL.md) 執行 Confirm Mode。

文件、模型輸出、全綠 CI 或沒有告警的 Production Telemetry，都不能單獨視為完成證據。

## Authority status

本 repository 目前仍是 **non-authoritative shadow**：

```text
authority.current       = NOTION_CANONICAL
repository_state        = SHADOW_NON_AUTHORITATIVE
cutover_decision        = pending
```

Notion 主層已壓縮為 Human Handbook + Archive。Archive 保留原技術契約與 pre-refactor snapshot，供 Phase 2 semantic reconciliation、audit 與 rollback 使用。

| Surface | 用途 |
|---|---|
| [Notion root](https://app.notion.com/p/382f5b2d1a9081e9a972f0b33fad3142) | 人類入口與 authority 狀態 |
| [Human Handbook](https://app.notion.com/p/3a2f5b2d1a9081f7a93ff2af3a6933a9) | 人類理解與採用 |
| [Archive](https://app.notion.com/p/399f5b2d1a9081afbeb3d7c07cabe014) | 舊版 technical contracts、audit、rollback source |
| [`governance/`](governance/README.md) | machine-readable shadow |
| [`governance/manifest.yaml`](governance/manifest.yaml) | authority、pipeline、artifacts、cutover preconditions |
| [`generated/notion-canonical-view.md`](generated/notion-canonical-view.md) | deterministic governance rendering |
| [`generated/semantic-reconciliation-report.md`](generated/semantic-reconciliation-report.md) | Phase 2 semantic comparison evidence |

Repository files do not change authority by their existence alone. Conflict must fail loudly; it must not silently choose a source.

## Phase 2 semantic reconciliation

Phase 2 introduces a reviewed, normalized projection of the archived Notion machine semantics:

- [`governance/reconciliation/notion-archive-baseline.yaml`](governance/reconciliation/notion-archive-baseline.yaml)
- [`scripts/semantic_reconcile.py`](scripts/semantic_reconcile.py)
- [`generated/semantic-reconciliation-report.md`](generated/semantic-reconciliation-report.md)
- [Phase 2 guide](docs/phase2-semantic-reconciliation.md)

Compared surface:

- Canonical five-Gate order.
- Upstream and auxiliary Gate boundaries.
- Intentionally undefined `GATE:TIA`.
- Stable ID canonical terms and namespaces.
- Gate scope, stage, and assertion keys.
- System and Change Profiles.
- Mandatory always-on controls.
- Frozen authority and pipeline invariants.

Current Phase 2 result: **`SEMANTIC_MATCH`**. This satisfies only the semantic-match precondition. Rollback dry run, observation-window design, and explicit Methodology Warden approval remain required before authority cutover.

## Canonical delivery flow

```text
Signal → GATE:ADMIT → Change Intent
  → Delta Spec → Impact Analysis → GATE:SPEC
  → Independent Test Generation → GATE:RED
  → AI Implementation → GATE:GREEN
  → Quality Verification → GATE:VDD
  → Controlled Deployment → GATE:DEPLOY
  → Production Verification → Signal / Accepted Evidence
```

The fixed pipeline is:

```text
GATE:SPEC → GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY
```

- `GATE:ADMIT` is upstream, not a sixth pipeline Gate.
- `GATE:REGRESSION` evaluates Agent workflow configuration and is auxiliary.
- Test Impact Analysis operates inside `GATE:GREEN`; `GATE:TIA` is intentionally undefined.

## 六項治理原則

1. 一項事實只定義一次；其他文件以 Stable ID 引用。
2. 規格變更先寫 Delta，再合併回 Canonical Spec。
3. 測試與實作權限分離；implementation Agent 不得弱化 test、threshold、policy、fixture 或 quarantine。
4. 品質門檻必須指定量測位置、環境、負載、percentile 與 threshold。
5. FEATURE／DEFECT 要有 Red Evidence；其他 Change Profile 要有核准的替代 evidence。
6. Production data 驗證 operational assumptions，不是 security、privacy、authorization 或 compliance 的唯一證明。

## 快速開始：Claude Code 模板

```bash
git clone https://github.com/trionnemesis/AI-NativeSTDD-VDD.git
cd AI-NativeSTDD-VDD
bash setup/init.sh /absolute/path/to/your-project
```

初始化後，在目標專案執行：

```text
閱讀 setup/AGENT_SETUP_PROTOCOL.md 並執行 Confirm Mode
```

如果只能靠 prompt 自律、缺少 runtime evidence，就不能宣稱治理已被強制執行。

## Repository surfaces

| Path | 內容與界線 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 相容性摘要；不得自行升格 repo authority |
| [`governance/`](governance/README.md) | Glossary、registries、Gates、profiles、schemas、reconciliation baseline |
| [`generated/`](generated/) | deterministic generated views and reconciliation evidence |
| [`setup/`](setup/AGENT_SETUP_PROTOCOL.md) | Confirm／Configure Mode 與安裝模板 |
| [`.claude/`](.claude/settings.json) | hooks、settings 與 verifier templates |
| [`integrations/codex/adapter.yaml`](integrations/codex/adapter.yaml) | opt-in Codex／Hermes mapping；不改 authority 或 pipeline |
| [`scripts/governance.py`](scripts/governance.py) | governance schema/reference/render validation |
| [`scripts/semantic_reconcile.py`](scripts/semantic_reconcile.py) | Archive baseline semantic comparison |
| [`scripts/codex_adapter.py`](scripts/codex_adapter.py) | Codex adapter deterministic validation |
| [`tests/`](tests/) | governance、reconciliation、adapter 與 hook regression tests |

## Validation

```bash
python3 -m pip install -r requirements-governance.txt
python3 scripts/governance.py validate
python3 scripts/governance.py render --check
python3 scripts/semantic_reconcile.py validate
python3 scripts/semantic_reconcile.py render --check
python3 scripts/codex_adapter.py validate
python3 -m unittest discover -s tests -v
```

These checks validate the repository-side shadow. They do not prove that a target repository has installed runtime hooks, nor do they perform authority cutover.

## 採用案例

- [AIhouskeeperagent](https://github.com/trionnemesis/AIhouskeeperagent)：專案層 Gate／hook 概念參考本治理系統；實際 enforcement 以該專案自身 evidence 為準。

## License

MIT
