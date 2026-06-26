# 04 · UI State Contract（UI 狀態契約）

---

## 概述

UI State Contract 是前端元件狀態的**機器可驗證規格**。它定義：
- 所有可能的 UI 狀態（state machine）
- 每個狀態下可見的 UI 元素
- 合法的狀態轉移（transitions）
- 視覺回歸測試的基準

---

## 為什麼需要 UI State Contract？

AI agent 常見問題：
1. 修改 API 後忘記同步更新 UI 狀態
2. 新增錯誤狀態但不知道要顯示什麼
3. 視覺回歸（CSS 改壞了但測試仍通過）

UI State Contract 解法：把 UI 狀態定義為 spec，機器驗證。

---

## UI State Contract 格式（`specs/contracts/ui/<name>.yaml`）

```yaml
id: "UI:LOGIN-FORM"
component: "LoginForm"
file: "src/components/LoginForm.tsx"
version: "1.2.0"

# 所有可能的狀態
states:
  idle:
    description: "初始狀態，等待使用者輸入"
    visible_elements:
      - id: "email-input"
        type: input
        required: true
      - id: "password-input"
        type: input
        required: true
      - id: "submit-button"
        type: button
        text: "登入"
        disabled: false
      - id: "error-message"
        visible: false

  loading:
    description: "送出中，等待 API 回應"
    visible_elements:
      - id: "submit-button"
        disabled: true
        text: "登入中..."
      - id: "loading-spinner"
        visible: true
      - id: "email-input"
        disabled: true
      - id: "password-input"
        disabled: true

  error:
    description: "登入失敗"
    visible_elements:
      - id: "error-message"
        visible: true
        text_pattern: "帳號或密碼錯誤"
      - id: "submit-button"
        disabled: false
      - id: "email-input"
        disabled: false

  success:
    description: "登入成功，準備重導"
    visible_elements:
      - id: "success-toast"
        visible: true
        text: "登入成功"

# 合法的狀態轉移
transitions:
  - from: idle
    to: loading
    trigger: "submit-button:click"
    condition: "email-input.valid && password-input.valid"

  - from: loading
    to: success
    trigger: "API:AUTH-V1 POST /login → 200"

  - from: loading
    to: error
    trigger: "API:AUTH-V1 POST /login → 401"

  - from: error
    to: loading
    trigger: "submit-button:click"

# 不允許的轉移（invariants）
forbidden_transitions:
  - from: success
    to: error
    reason: "成功後不應出現錯誤狀態"
  - from: idle
    to: success
    reason: "不允許繞過 loading 直接成功"

# 視覺回歸基準
visual_snapshots:
  tool: "playwright"           # 或 "storybook" / "percy"
  states_to_snapshot: ["idle", "loading", "error", "success"]
  viewport: { width: 1280, height: 720 }
  baseline_dir: "tests/visual-baseline/login-form/"
```

---

## 視覺回歸測試整合

### Playwright 範例

```python
# tests/test_login_form_visual.py
# REQ: UI:LOGIN-FORM
import pytest
from playwright.sync_api import Page

@pytest.fixture
def login_page(page: Page):
    page.goto("http://localhost:3000/login")
    return page

def test_idle_state_visual(login_page, snapshot):
    """BDD:LOGIN-UI-001 初始狀態視覺一致"""
    snapshot.assert_match(
        login_page.screenshot(),
        "login-form-idle.png"
    )

def test_loading_state_visual(login_page, snapshot):
    """BDD:LOGIN-UI-002 loading 狀態視覺一致"""
    login_page.fill("#email-input", "user@example.com")
    login_page.fill("#password-input", "password")
    # 攔截 API，讓其 pending
    with login_page.expect_request("**/api/v1/login"):
        login_page.click("#submit-button")
    snapshot.assert_match(
        login_page.screenshot(),
        "login-form-loading.png"
    )
```

---

## 狀態機驗證

### 測試所有合法轉移

```python
# tests/test_login_form_state_machine.py
# REQ: UI:LOGIN-FORM

VALID_TRANSITIONS = [
    ("idle", "loading"),
    ("loading", "success"),
    ("loading", "error"),
    ("error", "loading"),
]

FORBIDDEN_TRANSITIONS = [
    ("success", "error"),
    ("idle", "success"),
]

@pytest.mark.parametrize("from_state,to_state", VALID_TRANSITIONS)
def test_valid_transition(from_state, to_state):
    machine = LoginFormStateMachine()
    machine.set_state(from_state)
    assert machine.can_transition_to(to_state)

@pytest.mark.parametrize("from_state,to_state", FORBIDDEN_TRANSITIONS)
def test_forbidden_transition(from_state, to_state):
    machine = LoginFormStateMachine()
    machine.set_state(from_state)
    with pytest.raises(InvalidStateTransitionError):
        machine.transition_to(to_state)
```

---

## UI Contract 與 API Contract 的關聯

```yaml
# UI:LOGIN-FORM 依賴 API:AUTH-V1
dependencies:
  - contract: "API:AUTH-V1"
    endpoint: "POST /login"
    response_mapping:
      200: "success"
      401: "error"
      422: "error"
      500: "error"
```

當 API contract 變更（如 401 改為 403），UI contract 必須同步更新。  
Delta Spec 會追蹤此依賴。

---

## A/B 測試與 Variants

```yaml
id: "UI:LOGIN-FORM"
variants:
  - id: "control"
    description: "標準登入表單"
  - id: "phone-otp"
    description: "手機 OTP 登入（CR:2026-007）"
    requires_flag: "PHONE_LOGIN_ENABLED"
    states:
      # ... 額外狀態定義
```

---

*本章對應 Notion 頁面 04 · UI State Contract*
