# 02 · Canonical Spec（規格格式）

---

## Canonical Spec 是什麼？

Canonical Spec 是 STDD×VDD 中**唯一的規格來源**（Single Source of Truth）。  
每個需求、功能、API contract、UI 狀態都必須在 `specs/` 目錄下有對應的規格文件。

**核心規則**：`specs/` 目錄下的任何檔案，AI agent 不得修改（hook 強制）。

---

## 目錄結構

```
specs/
├── domain/             ← Domain entities & aggregates
│   ├── user.yaml
│   └── order.yaml
├── features/           ← BDD feature files（GATE:SPEC 驗證此目錄）
│   ├── user-login.feature
│   └── order-checkout.feature
├── contracts/          ← API & UI contracts
│   ├── api/
│   │   └── user-v2.yaml
│   └── ui/
│       └── login-form.yaml
├── quality/            ← Quality policies
│   └── coverage.yaml
├── decisions/          ← Architecture decision records
│   └── ADR-001.md
└── traceability/       ← Requirement traceability matrix
    └── matrix.yaml
```

---

## Domain Entity 格式（`specs/domain/<entity>.yaml`）

```yaml
id: "REQ:USER-ENTITY-001"
name: User
version: "1.0.0"
aggregate: true                  # 是否為 DDD Aggregate Root
bounded_context: "identity"

attributes:
  - name: id
    type: uuid
    invariants:
      - "INV:USER-ID-IMMUTABLE"
  - name: email
    type: string
    constraints:
      - format: email
      - unique: true

invariants:
  - id: "INV:USER-EMAIL-UNIQUE"
    description: "每個 email 只能對應一個 User"
    enforcement: database_unique_constraint

domain_events:
  - "SIG:USER_CREATED"
  - "SIG:USER_EMAIL_CHANGED"
```

---

## Feature File 格式（`specs/features/<module>.feature`）

```gherkin
# Feature ID: REQ:USER-LOGIN-001
# BDD: BDD:LOGIN-001

Feature: User Login
  以 email + password 登入系統

  Background:
    Given 系統中存在使用者 "user@example.com"

  @happy-path
  Scenario: BDD:LOGIN-001 成功登入
    Given 使用者在登入頁面
    When 輸入正確的 email "user@example.com" 和密碼 "correct-password"
    And 點擊登入按鈕
    Then 系統顯示歡迎訊息
    And 使用者被重導到 dashboard
    And 發出 SIG:USER_LOGGED_IN 事件

  @error-path
  Scenario: BDD:LOGIN-002 密碼錯誤
    Given 使用者在登入頁面
    When 輸入正確的 email 和錯誤的密碼
    And 點擊登入按鈕
    Then 顯示錯誤訊息 "帳號或密碼錯誤"
    And 不發出任何 Session 事件
```

---

## API Contract 格式（`specs/contracts/api/<name>.yaml`）

```yaml
id: "API:USER-V2"
version: "2.0.0"
locked: true                     # 鎖版後不可修改，需 Delta Spec
base_path: "/api/v2/users"

endpoints:
  - method: POST
    path: "/"
    request_schema:
      type: object
      required: [email, password]
      properties:
        email:
          type: string
          format: email
        password:
          type: string
          minLength: 8
    responses:
      200:
        schema_ref: "user-response-v2"
      400:
        schema_ref: "error-response"
      409:
        description: "Email already exists"

contract_tests:
  provider: "user-service"
  consumer: "web-frontend"
  pact_file: "tests/contracts/user-v2.pact.json"
```

---

## UI State Contract 格式（`specs/contracts/ui/<name>.yaml`）

詳見 [04-ui-state-contract.md](04-ui-state-contract.md)

---

## Quality Policy 格式（`specs/quality/coverage.yaml`）

```yaml
id: "QP:COVERAGE-001"
policy: coverage
thresholds:
  line: 80
  branch: 75
  function: 85
scope: "src/**/*.py"
enforcement: GATE:VDD
```

---

## Traceability Matrix（`specs/traceability/matrix.yaml`）

```yaml
# REQ → BDD → 測試 → 實作 的完整追蹤
entries:
  - req_id: "REQ:USER-LOGIN-001"
    bdd_ids: ["BDD:LOGIN-001", "BDD:LOGIN-002"]
    test_files: ["tests/test_user_login.py"]
    impl_files: ["src/auth/login.py"]
    api_contract: "API:USER-V2"
    status: "GREEN"
    vdd_attested: true
    attest_id: "ATTEST:LOGIN-001-VDD"
```

---

## Stable ID 規則

1. **永不重用**：刪除的 ID 不可分配給其他需求
2. **格式固定**：`NAMESPACE:DOMAIN-SEQUENCE`（例：`REQ:AUTH-001`）
3. **跨文件一致**：feature 文件、測試、實作註解中引用相同 ID
4. **版本升級**：API contract 改版用新 ID（`API:USER-V2`），舊版留存

---

*本章對應 Notion 頁面 02 · Canonical Spec*
