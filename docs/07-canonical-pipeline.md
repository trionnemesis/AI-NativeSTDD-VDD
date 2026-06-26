# 07 · Canonical Pipeline（權威 CI/CD Pipeline）

> **本章是 STDD×VDD pipeline 的權威定義。** 所有其他章節中提及的 pipeline 順序以本章為準。

---

## 5 閘門完整流程

```
GATE:ADMIT ──▶ GATE:SPEC ──▶ GATE:RED ──▶ GATE:GREEN ──▶ GATE:VDD ──▶ GATE:DEPLOY
   上游            #1            #2            #3            #4            #5
  探索分派         規格           紅燈          綠燈          驗證         部署確認
```

---

## GATE:ADMIT（探索分派循環，上游閘門）

**位置**：GATE:SPEC 的上游，獨立運作  
**觸發**：任何新需求、問題回報、功能請求  
**強制等級**：prompt-only

詳見 [14-discovery-dispatch-loop.md](14-discovery-dispatch-loop.md)

---

## GATE:SPEC — #1

**強制等級：runtime（PreToolUse hook）**

```
條件:
  specs/features/<module>.feature 存在且非空

Hook: pre_impl_gate.py
  - 攔截 Edit|Write 到 src/**
  - 確認對應 .feature 存在
  - exit 2 → 阻擋操作

AI Agent 動作:
  1. 確認 REQ/BDD IDs 存在於 specs/
  2. 若無 → 建立 spec 後再進行
  3. 不得在無 spec 情況下繞過
```

---

## GATE:RED — #2

**強制等級：runtime（PreToolUse hook）**

```
條件:
  .vdd/phase = RED_VERIFIED

Hook: pre_impl_gate.py（第二道檢查）
  - 讀取 .vdd/phase
  - 若非 RED_VERIFIED 或 GREEN → exit 2

AI Agent 動作:
  1. 委派 red-verifier subagent
  2. subagent 執行:
     a. pytest --co -k <test>（確認測試存在）
     b. pytest -k <test>（確認測試失敗）
  3. 存 .vdd/red/<req-id>.json（Red Evidence）
  4. 更新 .vdd/phase → RED_VERIFIED

注意: --co 和實跑是兩個步驟，不可合一
```

`.vdd/phase` 狀態機：

```
INIT → SPEC_VERIFIED → RED_VERIFIED → GREEN → VDD_PASS → DEPLOYED
```

---

## GATE:GREEN — #3

**強制等級：runtime（Stop hook）**

```
條件:
  pytest tests/ 全通過
  ruff check . clean

Hook: green_gate.py（Stop hook）
  - 每次 agent 嘗試結束時觸發
  - 若任一測試失敗或 lint 報錯 → block（繼續修）

AI Agent 禁止:
  - 弱化測試以通過此閘門
  - 跳過測試（pytest.skip）
  - 預期失敗（xfail）
  - 空斷言（assert True）
```

---

## GATE:VDD — #4

**強制等級：config/流程（CI pipeline + .vdd/phase）**

```
觸發: GATE:GREEN 通過後，CI 自動執行

Pipeline 步驟:
  1. pytest-cov: 覆蓋率 ≥ 80%
  2. mutmut run: 突變測試 ≥ 80%
  3. pytest -m integration: 整合測試
  4. pact-verifier: Contract 測試
  5. 產出 docs/vdd-report.md

Pass → .vdd/phase → VDD_PASS
Fail → CI fail，阻擋 merge
```

---

## GATE:DEPLOY — #5

**強制等級：架構性外建（Claude Code 無法強制）**

```
觸發: 部署到 Production 後

必要條件（需外建監控）:
  - SLO 在 24h 視窗內達成
  - 新增 Telemetry signals 有流量
  - 錯誤率 < 閾值

完成後:
  .vdd/phase → DEPLOYED
  寫入 ATTEST:<CR-ID>-DEPLOY 到 traceability
```

---

## CI Pipeline YAML 範例（GitHub Actions）

```yaml
# .github/workflows/stdd-vdd-pipeline.yml

name: STDD×VDD Pipeline

on:
  pull_request:
    branches: [main]

jobs:
  gate-spec:
    name: "GATE:SPEC — Spec exists"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify all src/ files have specs
        run: python scripts/check_spec_coverage.py

  gate-red:
    name: "GATE:RED — Red evidence exists"
    needs: gate-spec
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify red evidence for changed modules
        run: python scripts/check_red_evidence.py

  gate-green:
    name: "GATE:GREEN — All tests pass"
    needs: gate-red
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
      - run: ruff check .

  gate-vdd:
    name: "GATE:VDD — Quality gates"
    needs: gate-green
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt

      - name: Coverage
        run: pytest tests/ --cov=src --cov-fail-under=80
          --cov-report=json:coverage.json

      - name: Mutation Testing
        run: |
          mutmut run --paths-to-mutate src/
          python scripts/check_mutation_threshold.py --threshold 80

      - name: Integration Tests
        run: pytest tests/ -m integration -v
        env:
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

      - name: Contract Tests
        run: pact-verifier --provider-base-url=http://localhost:8000
          --pact-url=tests/contracts/

      - name: Generate VDD Report
        run: python scripts/generate_vdd_report.py

      - uses: actions/upload-artifact@v4
        with:
          name: vdd-report
          path: docs/vdd-report.md
```

---

## Phase 狀態檔（`.vdd/phase`）

`.vdd/phase` 是狀態機的持久化儲存，hook scripts 讀取此檔案：

```
INIT                ← 初始狀態
SPEC_VERIFIED       ← GATE:SPEC 通過
RED_VERIFIED        ← GATE:RED 通過（red evidence 存在）
GREEN               ← GATE:GREEN 通過（測試全過）
VDD_PASS            ← GATE:VDD 通過（CI 確認）
DEPLOYED            ← GATE:DEPLOY 通過（Telemetry 確認）
```

---

*本章是 STDD×VDD pipeline 的權威定義文件（Notion 頁面 07）*
