# 06 · 防偽測試策略（Anti-Fake Test）

---

## 問題：AI Agent 的假測試模式

AI agent 在 TDD 環境中的常見「偽造」行為：

| 模式 | 範例 | 問題 |
|------|------|------|
| **空斷言** | `assert True` | 永遠通過，無驗證 |
| **跳過測試** | `@pytest.skip("暫時跳過")` | 測試不執行 |
| **預期失敗** | `@pytest.mark.xfail` | 偽裝成「已知問題」 |
| **測試實作** | 測試直接呼叫實作邏輯作為斷言 | 測試與實作耦合 |
| **Mock 一切** | 所有依賴都 mock，包括業務邏輯 | 完全不測真實行為 |
| **先寫通過的測試** | 跳過 RED 階段 | 繞過 GATE:RED |

---

## 防偽策略 1：Red Evidence（最強防線）

Red Evidence 強制要求：**在任何實作開始前，測試必須真實失敗並留下機器可驗證的紀錄。**

`.vdd/red/<req-id>.json` 結構：

```json
{
  "requirement_id": "REQ:USER-LOGIN-001",
  "test_name": "test_login_with_valid_credentials",
  "baseline_commit_sha": "abc1234def5678",
  "failure_message": "FAILED tests/test_user_login.py::test_login_with_valid_credentials\nE   ImportError: cannot import name 'login' from 'src.auth'",
  "failure_location": "tests/test_user_login.py:23",
  "execution_timestamp": "2026-06-26T09:15:00Z",
  "pytest_output": "==================== 1 failed in 0.12s ====================="
}
```

**驗證規則**：
- `failure_message` 不得為空
- `baseline_commit_sha` 必須是實作前的 commit
- `execution_timestamp` 必須早於任何 `src/` 變更

---

## 防偽策略 2：Test Weakening Guard（hook）

`test_weakening_guard.py` 在每次測試檔案修改後偵測弱化 pattern：

```python
weakening_patterns = [
    (r"\bassert\s+True\b", "assert True（無效斷言）"),
    (r"@pytest\.skip", "pytest.skip（測試被跳過）"),
    (r"@unittest\.skip", "unittest.skip（測試被跳過）"),
    (r"\bxfail\b", "xfail（預期失敗標記）"),
    (r"\bpass\s*#.*assert", "pass 替代 assert"),
]
```

當前設定：發出 WARNING（不 block）。  
升級到 block：將 `sys.exit(0)` 改為 `sys.exit(2)`。

---

## 防偽策略 3：突變測試（Mutation Testing）

突變測試回答：「這個測試如果實作被改壞了，會失敗嗎？」

```
原始程式碼: if user.is_active and user.can_login:
突變 #1:    if user.is_active or user.can_login:   ← 邏輯改變
突變 #2:    if True:                               ← 條件消除
突變 #3:    if not user.is_active and user.can_login: ← 反轉
```

如果上述突變沒有讓測試失敗 → **測試無效**（escaped mutant）。

---

## 防偽策略 4：Contract Testing（防 Mock 濫用）

集成測試必須使用真實依賴或 Pact 合約，不允許 mock business logic：

```python
# ❌ 錯誤：mock 業務邏輯
def test_login(mocker):
    mocker.patch("src.auth.login", return_value={"token": "fake"})
    response = client.post("/login", data={...})
    assert response.status_code == 200  # 什麼都沒測到

# ✅ 正確：mock 外部依賴，測試真實邏輯
def test_login(mock_smtp, real_db):
    # mock_smtp：防止真實發信
    # real_db：使用真實資料庫
    response = client.post("/login", data={"email": "x@x.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["error"] == "帳號或密碼錯誤"
```

---

## 防偽策略 5：Traceability Matrix 追蹤

每個測試必須能追蹤到 REQ ID：

```python
# tests/test_user_login.py

def test_login_with_valid_credentials():
    """
    REQ: REQ:USER-LOGIN-001
    BDD: BDD:LOGIN-001
    """
    # 測試內容...
```

Traceability matrix 會驗證：每個 REQ 至少有一個對應測試。

---

## 偽測試偵測工具鏈

```
測試寫入時:
  test_weakening_guard.py (PostToolUse) → 偵測靜態 pattern

RED Gate 前:
  red-verifier subagent → 執行真實 pytest，取得失敗輸出

VDD 階段:
  mutmut → 偵測邏輯上無效的測試

CI 階段:
  pytest-cov → 確保覆蓋率
  pact-verifier → 確保 contract 測試真實
```

---

## 常見問題處理

### Q：測試因環境問題（DB 沒啟動）失敗，算 RED Evidence 嗎？

不算。Red Evidence 必須是**因缺少實作而失敗**（ImportError、NotImplementedError、AssertionError），不是環境錯誤（ConnectionError、PermissionError）。

### Q：可以用 `@pytest.mark.xfail(strict=True)` 嗎？

嚴格 xfail（strict=True）表示測試**預期失敗**，若通過反而報錯。  
這是合法的，但必須有 spec 說明此功能**刻意不實作**。

### Q：第三方服務的 mock 合法嗎？

合法，但 mock 必須符合對應的 API contract（Pact 合約）。  
直接 `mocker.patch("requests.get", return_value=anything)` 不合法。

---

*本章對應 Notion 頁面 06 · 防偽測試策略*
