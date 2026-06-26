# AI-Native STDD × VDD 工程治理系統

> **任何 Claude Code 專案可零摩擦套用的 AI-agent 治理層模板**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 是什麼？

這個 repo 是一套完整的 **Specification & Test-Driven Development × Verification & Validation-Driven Development（STDD×VDD）** 治理框架模板，專為 Claude Code CLI 環境設計。

- **STDD**：以 Canonical Spec + 先寫測試作為 hard constraint，限制 AI agent 的實作範圍
- **VDD**：Green 後的機器可驗證品質閘門，最終仲裁者是 Production Telemetry（**VDD ≠ Value-Driven，≠ Vulnerability-Driven**）

任何 Claude Code agent clone 這個 repo 後，讀 `CLAUDE.md` 即可自動初始化符合此治理流程的環境。

---

## 快速開始（30 秒）

```bash
# 1. Clone
git clone https://github.com/trionnemesis/AI-NativeSTDD-VDD.git
cd AI-NativeSTDD-VDD

# 2. 一鍵初始化（建目錄結構 + 複製 hooks）
bash scripts/init.sh

# 3. 讓 Claude Code agent 自動設定環境
# 在 Claude Code 中輸入：
# "閱讀 setup/AGENT_SETUP_PROTOCOL.md 並執行 Confirm Mode"
```

---

## 5 個規範閘門（Canonical Gates）

```
GATE:ADMIT ──▶ GATE:SPEC ──▶ GATE:RED ──▶ GATE:GREEN ──▶ GATE:VDD ──▶ GATE:DEPLOY
  (探索)          (規格)        (紅燈)         (綠燈)         (驗證)         (部署)
```

| Gate | 觸發條件 | 強制等級 | 說明 |
|------|---------|---------|------|
| `GATE:ADMIT` | 任何新需求進入 | prompt-only | Discovery & Dispatch Loop，07 上游 |
| `GATE:SPEC` | 寫實作前 | **runtime（hook deny）** | 必須有對應 `.feature` 檔 |
| `GATE:RED` | 進入實作前 | **runtime（hook deny）** | 測試必須當前失敗，存 `.vdd/red/*.json` |
| `GATE:GREEN` | 結束前 | **runtime（Stop hook block）** | 全測試通過 + lint clean |
| `GATE:VDD` | 合入主幹前 | config/流程 | 覆蓋率 + 突變測試 + 整合測試 |
| `GATE:DEPLOY` | 部署後 | 架構性外建 | Telemetry 閉環確認 |

---

## Repo 結構

```
AI-NativeSTDD-VDD/
├── README.md                    ← 本文件
├── CLAUDE.md                    ← Claude Code agent 指令（從這裡啟動）
├── docs/                        ← 14 章規格文件
│   ├── 00-canonical-glossary.md
│   ├── 01-method-architecture.md
│   ├── 02-canonical-spec.md
│   ├── 03-change-management.md
│   ├── 04-ui-state-contract.md
│   ├── 05-vdd-verification.md
│   ├── 06-anti-fake-test.md
│   ├── 07-canonical-pipeline.md
│   ├── 08-industry-comparison.md
│   ├── 09-agent-cli-evaluation.md
│   ├── 10-claude-code-implementation.md
│   ├── 11-headroom-context.md
│   ├── 12-ai-agent-readiness-gate.md
│   ├── 13-self-healing-ci.md
│   └── 14-discovery-dispatch-loop.md
├── .claude/                     ← Claude Code 設定
│   ├── settings.json            ← Hook 註冊模板
│   ├── hooks/                   ← 6 個 Python hook scripts
│   │   ├── pre_impl_gate.py     ← SPEC + RED Gate（PreToolUse Edit/Write）
│   │   ├── bash_guard.py        ← Bash bypass 防護
│   │   ├── green_gate.py        ← GREEN 完成門（Stop hook）
│   │   ├── test_weakening_guard.py ← 測試弱化偵測
│   │   ├── inject_spec.py       ← Spec diff 注入（UserPromptSubmit）
│   │   └── reinject_rules.py    ← Compaction 後重注入
│   └── agents/
│       └── red-verifier.md      ← 唯讀 RED 驗證 subagent
├── setup/
│   ├── AGENT_SETUP_PROTOCOL.md  ← AI agent 入口文件
│   ├── init.sh                  ← 一鍵初始化腳本
│   └── templates/
│       ├── managed-settings.json ← macOS org-level config（P0）
│       └── mcp.json             ← Oracle MCP server config
└── scripts/
    └── init.sh                  ← 快捷符號連結
```

---

## 給 AI Agent 的說明

clone 後，在 Claude Code 中執行：

```
閱讀 setup/AGENT_SETUP_PROTOCOL.md 並執行 Confirm Mode，確認環境後進入 Configure Mode 完成 P0–P6 設定。
```

`CLAUDE.md` 會被 Claude Code 自動載入，包含完整的閘門規則與禁止行為。

---

## 給人類開發者的說明

### 環境需求

- Claude Code CLI（最新版）
- Python 3.9+（hook scripts 依賴）
- `pytest`, `ruff`（GREEN Gate 依賴）
- macOS：需管理員權限安裝 `managed-settings.json`

### 手動設定步驟

```bash
# P0: org-level 強制設定（macOS，需管理員）
sudo cp setup/templates/managed-settings.json \
  "/Library/Application Support/ClaudeCode/managed-settings.json"

# P1: 建目錄結構
mkdir -p specs/{domain,features,contracts,quality,decisions,traceability}
mkdir -p .vdd/red
echo "INIT" > .vdd/phase

# P2: 複製 hooks 到目標專案
mkdir -p .claude/hooks
cp .claude/hooks/*.py <your-project>/.claude/hooks/

# P3: 複製 settings.json
cp .claude/settings.json <your-project>/.claude/settings.json

# P4: 安裝 subagent
mkdir -p <your-project>/.claude/agents
cp .claude/agents/red-verifier.md <your-project>/.claude/agents/
```

---

## Autonomy Tiers（自主性等級）

| Tier | 行為 | 觸發條件 |
|------|------|---------|
| **T1** | auto-PR，無須人工介入 | 無破壞性變更、覆蓋率 >80% |
| **T2（預設）** | auto-PR + 強制人工 review | 任何規格變更、新 domain entity |
| **T3** | 禁止 auto-dispatch | schema migration、auth 變更、pricing 邏輯 |

fallthrough 預設 = **T2**。

---

## 文件索引

| 章節 | 文件 | 主題 |
|------|------|------|
| 00 | [Canonical Glossary](docs/00-canonical-glossary.md) | 所有術語的唯一定義 |
| 01 | [Method Architecture](docs/01-method-architecture.md) | 方法論架構與 5 層技術棧 |
| 02 | [Canonical Spec](docs/02-canonical-spec.md) | 規格格式、Stable ID 系統 |
| 03 | [Change Management](docs/03-change-management.md) | Delta Spec 變更套件 |
| 04 | [UI State Contract](docs/04-ui-state-contract.md) | UI 狀態契約與視覺回歸 |
| 05 | [VDD Verification](docs/05-vdd-verification.md) | VDD 品質驗證體系 |
| 06 | [Anti-Fake Test](docs/06-anti-fake-test.md) | 防偽測試策略 |
| 07 | [Canonical Pipeline](docs/07-canonical-pipeline.md) | 權威 CI/CD pipeline（5 閘門）|
| 08 | [Industry Comparison](docs/08-industry-comparison.md) | 12 維度業界比較矩陣 |
| 09 | [Agent CLI Evaluation](docs/09-agent-cli-evaluation.md) | 28 criteria Agent CLI 評估 |
| 10 | [Claude Code Implementation](docs/10-claude-code-implementation.md) | Claude Code 具體實作方式 |
| 11 | [Headroom Context](docs/11-headroom-context.md) | Context 壓縮層設計 |
| 12 | [AI Agent Readiness Gate](docs/12-ai-agent-readiness-gate.md) | 7 phase 部署就緒檢查 |
| 13 | [Self-Healing CI](docs/13-self-healing-ci.md) | 自癒 CI 成熟度階梯 |
| 14 | [Discovery & Dispatch Loop](docs/14-discovery-dispatch-loop.md) | GATE:ADMIT 探索分派循環 |

---

## 原始規格

[AI-Native STDD × VDD 工程治理系統](https://www.notion.so/AI-Native-STDD-VDD-382f5b2d1a9081e9a972f0b33fad3142) — Notion  
整合版：本 repo（2026-06-26）
