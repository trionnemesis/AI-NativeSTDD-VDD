# 03 · 變更管理（Change Management）

---

## Delta Spec 變更套件

每個規格變更（需求新增/修改/刪除）必須包裝為 **Delta Spec**，不允許直接修改 spec 文件而不建立 Delta Spec。

### Delta Spec 結構

```
changes/<CR:ID>/
├── intent.md              ← 變更意圖（What + Why）
├── delta.yaml             ← 機器可讀的變更宣告
├── impact.md              ← 影響分析（破壞性/非破壞性）
├── acceptance.feature     ← 驗收標準（BDD 格式）
└── verification-plan.yaml ← VDD 驗證計畫
```

---

## intent.md 格式

```markdown
# CR:2026-007 — 新增電話號碼登入

## 變更意圖
允許使用者以手機號碼 + OTP 登入，作為 email/password 的替代方案。

## 動機
- 行動裝置用戶的轉換率低於預期（SIG:LOGIN_CONVERSION_RATE < 0.7）
- 競品分析顯示手機登入提升 23% 轉換率

## 範圍
- 新增 API:AUTH-PHONE-V1
- 修改 UI:LOGIN-FORM（新增 tab）
- 新 domain logic：PhoneOTP aggregate

## 不在範圍
- 社群登入（Google/Apple）
- 兩步驟驗證的合併
```

---

## delta.yaml 格式

```yaml
id: "CR:2026-007"
title: "新增電話號碼登入"
version: "1.0.0"
tier: "T2"                        # Autonomy Tier
breaking_change: false

adds:
  - type: api_contract
    id: "API:AUTH-PHONE-V1"
    file: "specs/contracts/api/auth-phone-v1.yaml"
  - type: bdd_scenario
    ids: ["BDD:PHONE-LOGIN-001", "BDD:PHONE-LOGIN-002"]
    file: "specs/features/phone-login.feature"

modifies:
  - type: ui_contract
    id: "UI:LOGIN-FORM"
    field: "variants"
    from: ["email-password"]
    to: ["email-password", "phone-otp"]

removes: []

deprecates: []

invariants_checked:
  - "INV:AUTH-ONE-SESSION-PER-USER"
  - "INV:PHONE-UNIQUE"
```

---

## impact.md 格式

```markdown
# CR:2026-007 影響分析

## 破壞性評估
**結論：非破壞性變更**

- API:USER-V2 不受影響（新增獨立 endpoint）
- UI:LOGIN-FORM 向下相容（新增 tab，不移除現有流程）
- 資料庫：新增 phone_verifications 表（pure add）

## 受影響的現有測試
- tests/test_user_login.py：不需修改
- tests/test_auth_middleware.py：需新增 phone OTP 測試案例

## 相依服務
- SMS Gateway（新依賴）：需要 mock 在測試環境
- Rate Limiting Service：需擴充 phone OTP 限制規則

## 回滾計畫
Feature flag: `PHONE_LOGIN_ENABLED`（預設 false）
回滾：設定 `PHONE_LOGIN_ENABLED=false` 即可
```

---

## acceptance.feature 格式

```gherkin
# CR:2026-007 驗收標準

Feature: 電話號碼登入
  REQ: CR:2026-007
  Tier: T2

  Scenario: BDD:PHONE-LOGIN-001 成功 OTP 登入
    Given 使用者已驗證手機號碼 "+886912345678"
    When 請求 OTP 到該號碼
    And 在 5 分鐘內輸入正確的 6 位數 OTP
    Then 系統發出 SIG:USER_LOGGED_IN 事件
    And Session token 有效期為 24 小時

  Scenario: BDD:PHONE-LOGIN-002 OTP 逾時失敗
    Given 使用者收到 OTP
    When 5 分鐘後才輸入 OTP
    Then 顯示錯誤 "驗證碼已失效，請重新發送"
    And 不建立 Session
```

---

## verification-plan.yaml 格式

```yaml
id: "CR:2026-007-VDP"
linked_cr: "CR:2026-007"

unit_tests:
  - target: "src/auth/phone_otp.py"
    scenarios: ["BDD:PHONE-LOGIN-001", "BDD:PHONE-LOGIN-002"]
    coverage_target: 85

integration_tests:
  - target: "tests/integration/test_phone_auth.py"
    requires: ["sms-gateway-mock", "redis"]

contract_tests:
  - consumer: "web-frontend"
    provider: "auth-service"
    pact: "tests/contracts/phone-auth.pact.json"

mutation_testing:
  scope: "src/auth/phone_otp.py"
  threshold: 80

telemetry_signals:
  - signal: "SIG:USER_LOGGED_IN"
    attribute: "method=phone_otp"
    validation: "count > 0 within 24h after deploy"
  - signal: "SIG:PHONE_OTP_FAILURE_RATE"
    slo: "< 5%"
```

---

## 變更審核流程

```
建立 CR:ID → 填寫 Delta Spec 套件
      ↓
T3？ → 人工審核（必須）
T2？ → auto-PR + human review（必須）
T1？ → auto-PR（無需 review）
      ↓
GATE:SPEC 更新：合入新 spec 檔案
      ↓
GATE:RED：紅燈驗證
      ↓
GATE:GREEN：實作完成
      ↓
GATE:VDD：verification-plan 執行
      ↓
GATE:DEPLOY：Telemetry 閉環
      ↓
ATTEST:CR-<ID>-VDD 寫入 traceability
```

---

## 不允許的變更模式

1. **直接修改 `specs/` 下的檔案而不建立 CR**
2. **backward-incompatible 變更沒有 Delta Spec**
3. **刪除 Stable ID**（可 deprecate，不可刪除）
4. **T3 變更在沒有人工審核下 auto-dispatch**

---

*本章對應 Notion 頁面 03 · 變更管理*
