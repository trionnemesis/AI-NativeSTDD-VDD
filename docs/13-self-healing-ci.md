# 13 · 自癒 CI（Self-Healing CI）

---

## 概述

Self-Healing CI 是 STDD×VDD 的進階特性，讓 CI pipeline 能在測試失敗時**自動診斷並嘗試修復**，而不只是報告失敗。

---

## 成熟度階梯（Maturity Ladder）

```
Level 1: Observer    ← 偵測失敗，回報，不修復
Level 2: Gatekeeper  ← 偵測失敗，阻擋合入，分類失敗
Level 3: Healer      ← 偵測失敗，自動修復（Full phase 才開放）
```

**重要**：Healer 模式只在組織完成 Full phase 導入後啟用，確保治理框架已完整。

---

## Level 1：Observer

**能力**：偵測 + 分類 + 回報

```yaml
# .github/workflows/observer.yml
- name: Test failure analysis
  if: failure()
  run: |
    python3 scripts/analyze_failure.py \
      --junit-xml test-results.xml \
      --output failure-report.md

- name: Comment on PR
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      const report = fs.readFileSync('failure-report.md', 'utf8')
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        body: `## CI Failure Analysis\n\n${report}`
      })
```

失敗分類：

```python
# scripts/analyze_failure.py
FAILURE_CATEGORIES = {
    "ImportError": "missing_implementation",
    "AssertionError": "logic_error",
    "ConnectionError": "environment_issue",
    "TimeoutError": "flaky_test",
}
```

---

## Level 2：Gatekeeper

**能力**：Observer + 阻擋合入 + 強制修復路徑

```yaml
# 閘門設定
branch_protection:
  required_status_checks:
    - "GATE:SPEC"
    - "GATE:RED (evidence exists)"
    - "GATE:GREEN (all tests pass)"
    - "GATE:VDD (quality gates)"
  enforce_admins: true
  required_pull_request_reviews:
    required_approving_review_count: 1
```

失敗路由：

```
測試失敗
  ↓
categorize_failure()
  ↓
  ├── environment_issue → 觸發環境重建 workflow
  ├── flaky_test        → 標記為 flaky，加入監控清單
  ├── logic_error       → 分派給 agent 診斷（Level 3）
  └── missing_impl      → 確認 .vdd/phase，提示執行 RED
```

---

## Level 3：Healer（Full Phase Only）

**能力**：Gatekeeper + 自動修復

**前提**：
- 組織已完成 7 phase 設定（P0–P6）
- 所有 specs 完整（GATE:SPEC 通過）
- 團隊已建立 Red Evidence 習慣（GATE:RED 通過率 > 90%）

### 自動修復工作流

```yaml
# .github/workflows/healer.yml
name: Self-Healing CI

on:
  workflow_run:
    workflows: ["STDD×VDD Pipeline"]
    types: [completed]

jobs:
  heal:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download failure report
        uses: actions/download-artifact@v4
        with:
          name: failure-report

      - name: Dispatch healing agent
        run: |
          python3 scripts/dispatch_healer.py \
            --failure-report failure-report.json \
            --tier $(cat .vdd/phase)
```

`dispatch_healer.py` 邏輯：

```python
def dispatch_healer(failure_report, current_phase):
    category = failure_report["category"]

    if category == "environment_issue":
        # 非 agent 問題，重建環境
        rebuild_environment()

    elif category == "flaky_test":
        # 分析 flakiness，加入隔離列表
        mark_as_flaky(failure_report["test_name"])

    elif category == "logic_error" and current_phase == "GREEN":
        # 安全範圍內的自動修復
        # 必須仍在已有 spec 和 Red Evidence 的範圍內
        dispatch_agent_fix(
            spec=failure_report["related_spec"],
            red_evidence=failure_report["red_evidence"],
            error=failure_report["error_message"]
        )

    elif category == "missing_implementation":
        # 不自動修復，提示人工確認 RED Gate
        notify_missing_red_evidence(failure_report)
```

---

## 自癒邊界（什麼不自動修復）

| 場景 | 原因 |
|------|------|
| T3 Autonomy 需求的失敗 | 必須人工決策 |
| schema migration 失敗 | 不可逆操作 |
| Red Evidence 不存在 | 不確定是否進入 RED Gate |
| 修復需要新增測試 | 觸發完整 GATE:RED 流程 |
| 涉及 auth/payment 邏輯 | 安全關鍵，必須人工 |

---

## Flaky Test 管理

```yaml
# .vdd/flaky-tests.yaml
flaky_tests:
  - id: "tests/test_email_service.py::test_send_notification"
    reason: "外部 SMTP 服務偶發超時"
    first_seen: "2026-06-01"
    occurrences: 5
    action: "quarantine"         # 隔離，不計入 GATE:GREEN
    resolution: "mock SMTP in test environment"
    status: "pending"
```

隔離的 flaky test 不計入 GATE:GREEN，但必須在 VDD Report 中記錄。

---

## 自癒 CI 的 ROI

導入 Healer 模式後的典型指標：

| 指標 | Before | After |
|------|--------|-------|
| MTTR（平均修復時間）| 4h | 0.5h |
| CI 失敗需人工介入比例 | 80% | 35% |
| Flaky test 誤報 | 20% CI runs | < 5% CI runs |
| Dev 等待 CI 結果時間 | 平均 45min | 平均 15min |

---

*本章對應 Notion 頁面 13 · 自癒 CI*
