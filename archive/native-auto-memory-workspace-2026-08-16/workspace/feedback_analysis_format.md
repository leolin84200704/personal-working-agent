---
name: feedback-analysis-format
description: "**IRON RULE** Ticket analysis 必須先用 4 部結構打開：目的 / 改之前 / 改之後為何有效 / 改什麼東西。tech-detail 放最後。VP-16832 違反一次 Leo 再次強調"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd572592-84d4-40cc-b380-44631eaf282a
---

# IRON RULE

任何 ticket analysis（LIS Work Loop Step 2 / Step 4 報告 / 任何「我分析了 ticket，這是結果」的訊息）**必須先用以下 4 部結構打開**，再進其他 detail：

1. **目的** — PM 想達到什麼 user-facing 效果（不是 AC 字面複述，是底層意圖）
2. **改之前長什麼樣子** — current state / behavior，最好包含具體 user 路徑或 system 行為
3. **改之後為什麼能達到這個效果** — change → effect 的 causal link，講清楚為什麼這樣改就會產生 PM 想要的效果
4. **要透過改什麼東西完成需求** — 具體動哪個 file / table / endpoint / field / config

**順序固定**：1 → 2 → 3 → 4。先講白話 user-facing 邏輯，再講 tech detail。

## Why

Leo 原話：「不然這樣我看不懂」。

純 tech 報告（endpoint X 改 Y / table Z 加 column W）隱藏「為什麼這樣做」+「對 user 影響」。Leo 是 reviewer，要先看到 PM intent 跟 cause→effect 才能判斷我有沒有抓對方向。

## 重犯紀錄

- 2026-06-04 VP-16832 Step 4 報告 — 用「分析摘要 / 可以複用 / 缺的東西 / unknown / 建議方案」結構，**沒用 4 部開頭**。Leo 直接點出。
- 之前已存過這條 memory 但實際操作沒套 — **這條是 IRON，每 ticket 強制檢查 self-output 有沒有這 4 段**。

## How to apply

- Step 4 報告 template:

```
## Ticket: {id} — {title}

### 目的
{PM 想達到什麼效果，user-facing 講白話}

### 改之前長什麼樣子
{current state 描述}

### 改之後為什麼能達到這個效果
{causal link：A 改 B 後，system 行為變成 C，因此 user 看到 D}

### 要透過改什麼東西完成需求
{具體 file:line / table column / endpoint / config}

### 其他必要 detail（unknowns / 風險 / approach 比較 etc）
```

Tech-only report 是 anti-pattern。Related: [[feedback_agent_workflow]]
