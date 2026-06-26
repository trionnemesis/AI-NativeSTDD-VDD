# 05 · VDD 驗證體系（Verification & Validation）

---

## VDD 的定義（再次確認）

> **VDD = Verification & Validation-Driven Development**

- **Verification**（驗證）：「我們是否正確地建造了系統？」— 機器可驗證的品質指標
- **Validation**（確效）：「我們是否建造了正確的系統？」— Production Telemetry 確認

**重申：VDD ≠ Value-Driven，≠ Vulnerability-Driven**

---

## VDD 閘門觸發時機

```
GATE:GREEN 通過後
      ↓
VDD Pipeline 啟動（CI 自動觸發）
      ↓
VDD Report 產出
      ↓
GATE:VDD ← Pass/Fail
      ↓（Pass）
GATE:DEPLOY 準備
```

---

## VDD 品質層（4 維度）

### 維度 1：覆蓋率（Coverage）

```yaml
# specs/quality/coverage.yaml
thresholds:
  line: 80
  branch: 75
  function: 85
scope: "src/**/*.py"
```

**工具**：`pytest-cov`、`coverage.py`

```bash
pytest tests/ --cov=src --cov-report=json:coverage.json \
  --cov-fail-under=80
```

### 維度 2：突變測試（Mutation Testing）

目的：確保測試**真的在測試**，而非只是執行到程式碼。

```yaml
# specs/quality/mutation.yaml
id: "QP:MUTATION-001"
tool: "mutmut"
scope: "src/"          # 全域（changed-code 優先）
threshold: 80          # escaped mutant < 20%
critical_domains:      # 必須 100% kill
  - "src/auth/"
  - "src/payments/"
```

Escaped mutant 處理規則：
- 非 critical domain：記錄 disposition（`ATTEST:MUTANT-<id>-ACCEPTED` + 理由）
- Critical domain：**必須修正測試，不允許豁免**

```bash
mutmut run --paths-to-mutate src/
mutmut results  # 查看 escaped mutants
```

### 維度 3：整合測試（Integration Tests）

針對系統邊界（資料庫、外部 API、事件佇列）：

```python
# tests/integration/test_user_service.py
# REQ: REQ:USER-LOGIN-001
# 整合測試：不 mock 資料庫

@pytest.mark.integration
def test_login_persists_session(real_db, real_redis):
    """BDD:LOGIN-001 登入後 session 確實寫入 Redis"""
    user = create_test_user(real_db, email="test@example.com")
    response = login(real_db, real_redis, email="test@example.com",
                     password="correct")
    assert response.status_code == 200
    session_key = f"session:{response.json()['token']}"
    assert real_redis.exists(session_key)
```

### 維度 4：Contract Testing

```bash
# Pact 合約測試
pytest tests/contracts/ -v
pact-verifier --provider-base-url=http://localhost:8000 \
  --pact-url=tests/contracts/user-v2.pact.json
```

---

## VDD Report 格式

CI 產出 `docs/vdd-report.md`：

```markdown
# VDD Report — CR:2026-007

**日期**: 2026-06-26
**Commit**: abc1234

## Summary
| 維度 | 結果 | 閾值 | Pass/Fail |
|------|------|------|-----------|
| Coverage (line) | 83% | 80% | ✅ PASS |
| Coverage (branch) | 77% | 75% | ✅ PASS |
| Mutation Score | 82% | 80% | ✅ PASS |
| Integration Tests | 45/45 | all | ✅ PASS |
| Contract Tests | 3/3 | all | ✅ PASS |

## Mutation Testing
- Total mutants: 156
- Killed: 128 (82%)
- Escaped: 28 (18%)
- Critical domain escaped: 0 ✅

## Escaped Mutants Disposition
| Mutant ID | File | Disposition | Reason |
|-----------|------|-------------|--------|
| MUTANT-042 | src/utils/format.py:L23 | ACCEPTED | 純格式函數，無業務邏輯 |

## Attestation
ATTEST:CR-2026-007-VDD — 2026-06-26T10:30:00Z
Attested by: CI/CD pipeline (SHA: abc1234)
```

---

## Telemetry 閉環（Validation 層）

VDD 的最終仲裁者是 Production Telemetry，但這超出 Claude Code 的執行範疇：

```yaml
# verification-plan.yaml 中的 telemetry_signals
telemetry_signals:
  - signal: "SIG:USER_LOGGED_IN"
    slo: "error_rate < 1%"
    validation_window: "24h after deploy"
    owner: "oncall"
```

監控工具：Datadog、Grafana、Prometheus（需外建）

---

## Attestation 記錄

每個 VDD 通過的 CR 必須有 Attestation：

```yaml
# specs/traceability/matrix.yaml
- req_id: "REQ:USER-LOGIN-001"
  attest_id: "ATTEST:LOGIN-001-VDD"
  attested_at: "2026-06-26T10:30:00Z"
  vdd_pass: true
  telemetry_validated: true
  notes: "Production 24h SLO 確認通過"
```

---

*本章對應 Notion 頁面 05 · VDD 驗證體系*
