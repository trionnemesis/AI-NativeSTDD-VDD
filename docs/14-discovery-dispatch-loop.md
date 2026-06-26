# 14 · Discovery & Dispatch Loop（GATE:ADMIT）

---

## 概述

GATE:ADMIT 是 STDD×VDD pipeline 的**上游閘門**，在 GATE:SPEC 之前運作。

它回答的問題：「這個需求是否清楚到可以開始寫規格？」

---

## GATE:ADMIT 的定位

```
使用者/PM 提出需求
        ↓
   GATE:ADMIT ← 本章
  Discovery & Dispatch Loop
        ↓（通過）
   GATE:SPEC（寫規格）
        ↓
   [GATE:RED → GATE:GREEN → GATE:VDD → GATE:DEPLOY]
```

GATE:ADMIT **不是 GATE:SPEC 的一部分**，它是獨立的上游閘門。

---

## 4 個 Admit 活動

### Admit-1：需求探索（Discovery）

確認需求的完整性：

```yaml
# ADMIT:001 探索清單
admit_id: "ADMIT:001"
raw_request: "讓使用者可以用手機登入"

discovery_questions:
  - "手機登入是替代還是補充現有 email 登入？"
  - "OTP 或密碼？OTP 的有效期多長？"
  - "手機號碼是否需要事先驗證才能設定？"
  - "失敗嘗試次數上限是多少？"
  - "是否需要兩步驟驗證的整合？"

answers: {}                  # 由 PM/使用者回答
status: "pending_answers"
```

### Admit-2：衝突偵測（Conflict Detection）

與現有規格的衝突分析：

```python
# scripts/conflict_detector.py
def detect_conflicts(new_feature_description):
    """
    掃描 specs/ 確認新功能不衝突現有 invariants
    """
    relevant_specs = search_specs(new_feature_description)
    for spec in relevant_specs:
        conflicts = check_invariant_violations(new_feature_description, spec)
        if conflicts:
            return ConflictReport(spec_id=spec.id, conflicts=conflicts)
    return None
```

常見衝突類型：
- 與現有 `INV:` invariant 衝突
- 與現有 API contract 版本衝突
- 與現有 UI State Contract 的狀態機衝突

### Admit-3：Tier 分類（Tier Classification）

決定 Autonomy Tier：

```
新需求 → 是否涉及 schema migration / auth / pricing？
  YES → T3（人工審核必須，禁止 auto-dispatch）
  NO  → 是否有規格變更或新 domain entity？
          YES → T2（auto-PR + human review）
          NO  → T1（auto-PR）
  
不確定 → T2（預設）
```

### Admit-4：Delta Spec 建立（Spec Kickoff）

Admit 通過後，建立 Delta Spec 套件骨架：

```bash
# scripts/new_cr.sh <CR-ID> "<title>"
CR_ID=$1
TITLE=$2

mkdir -p "changes/$CR_ID"
cat > "changes/$CR_ID/intent.md" <<EOF
# $CR_ID — $TITLE

## 變更意圖
（待填入）

## 動機
（待填入）
EOF

cat > "changes/$CR_ID/delta.yaml" <<EOF
id: "$CR_ID"
title: "$TITLE"
tier: "T2"          # 預設 T2，確認後修改
status: "draft"
EOF

echo "ADMIT:$CR_ID" >> .vdd/admit-queue
```

---

## Dispatch 決策矩陣

GATE:ADMIT 通過後的分派路由：

| Tier | Admit 狀態 | 行動 |
|------|-----------|------|
| T1 | 完整資訊 | 直接 dispatch agent → GATE:SPEC |
| T2 | 完整資訊 | dispatch agent → GATE:SPEC + 設定 PR review 規則 |
| T3 | 完整資訊 | **停止**，等待人工 review + 明確授權 |
| 任何 | 資訊不足 | 回到 Discovery，繼續問問題 |

---

## ADMIT 狀態機

```
raw_request
    ↓
ADMIT:DISCOVERING    ← 問題清單未完整回答
    ↓（問題已回答）
ADMIT:CONFLICT_CHECK ← 掃描現有 specs 衝突
    ↓（無衝突）
ADMIT:TIER_ASSIGNED  ← Tier 分類完成
    ↓
ADMIT:SPEC_KICKOFF   ← Delta Spec 骨架建立
    ↓
ADMIT:DISPATCHED     ← 進入 GATE:SPEC
```

---

## Admit Queue 管理

`.vdd/admit-queue` 記錄待處理的 ADMIT items：

```
ADMIT:2026-001   # 手機登入
ADMIT:2026-002   # 訂單取消功能
ADMIT:2026-003   # 報表匯出
```

Agent 每次啟動時可以：

```bash
# 查看待處理的 ADMIT items
cat .vdd/admit-queue

# 查看特定 CR 的 Admit 狀態
cat changes/CR:2026-007/intent.md
cat changes/CR:2026-007/delta.yaml
```

---

## Admit 清單模板（`ADMIT:ID` spec 格式）

```yaml
id: "ADMIT:2026-001"
raw_request: "讓使用者可以用手機登入"

# 4 個 Admit 活動狀態
discovery:
  status: "complete"
  questions_answered: 5
  answers_file: "changes/CR:2026-007/discovery-answers.md"

conflict_check:
  status: "complete"
  conflicts_found: 0
  checked_against: ["INV:AUTH-ONE-SESSION-PER-USER", "API:USER-V2"]

tier:
  assigned: "T2"
  reason: "新增 domain entity（PhoneOTP），需 human review"

spec_kickoff:
  status: "complete"
  cr_id: "CR:2026-007"
  delta_spec_path: "changes/CR:2026-007/"

dispatch:
  status: "dispatched"
  dispatched_at: "2026-06-26T09:00:00Z"
  target_gate: "GATE:SPEC"
```

---

## 與 GATE:SPEC 的邊界

| | GATE:ADMIT | GATE:SPEC |
|---|-----------|----------|
| **輸入** | 原始需求（自然語言）| Canonical Spec 草稿 |
| **輸出** | 可以開始寫規格的確認 | 完整 .feature 文件 |
| **強制等級** | prompt-only | runtime hook |
| **執行者** | PM + Agent 協作 | 純 Agent |
| **目標** | 需求完整性 + Tier 分類 | 規格完整性 |

---

*本章對應 Notion 頁面 14 · Discovery & Dispatch Loop（GATE:ADMIT 上游閘門）*
