"""
Flow prompts — the instructions that drive each workflow.

These go directly to Claude Code CLI via `claude -p`.
Claude Code has access to:
- Native tools: Bash, Read, Edit, Write, Grep, Glob
- Vibrant MCP Server: fetch_and_summarize_ticket, mysql_query,
  search_audit_log, query_general_sample_events, Sentry, Datadog, etc.

Design principles:
- Goal-oriented: 定義目標和約束，不定義步驟
- Self-planning: model 自己拆解任務，根據實際情況調整
- Explicit reflection: 每個關鍵步驟後強制寫出理解和缺口
"""

# ---------------------------------------------------------------------------
# Reflection protocol — shared across all prompts
# ---------------------------------------------------------------------------
_REFLECTION_PROTOCOL = """
## 反思協議（每個關鍵動作後必須執行）

每次呼叫工具拿到結果後，在決定下一步之前，先寫出以下反思區塊：

```
【反思】
✅ 目前確認的事實：[列出已經確認的資訊]
❓ 還不確定/缺少的：[列出還需要查的東西]
🔄 計劃調整：[原本計劃是否需要改變？為什麼？]
➡️ 下一步：[基於以上，決定下一個動作]
```

**為什麼要這樣做：**
- 避免看到第一個結果就跳到結論
- 強迫自己檢查「還有什麼沒查到」
- 根據實際發現的資訊調整策略，而不是死板照步驟走
"""

# ---------------------------------------------------------------------------
# Domain constraints — injected into prompts that need business rules
# ---------------------------------------------------------------------------
_DOMAIN_CONSTRAINTS = """
## 領域約束（必須遵守）

### EMR Integration 關鍵規則
- **Provider ID ≠ Practice ID** — 永遠不要搞混
- Provider ID → `ehr_integrations.customer_id`, `order_clients.customer_id`
- Practice ID → `order_clients.clinic_id`（不是 customer_id！）
- Provider Name 必須從 gRPC 查（192.168.60.6:30276），ticket 裡的 Name 通常是 clinic name
- NPI 也必須從 gRPC 查
- msh06 預設=Provider ID，除非 ticket 明確說用 Practice ID

### EMR 相關 ticket → 優先看 lis-backend-emr-v2 和 EMR-Backend
- "New EMR Integration" → 主要是 DB 操作（ehr_integrations, order_clients, sftp_folder_mapping）
- "No results received" → 先查 ehr_integrations 有沒有設定
- "Repush results" → 看 lis-backend-emr-v2 的 result 推送邏輯

### Git 安全
- 只在自己的 branch 操作（feature/leo/*, bugfix/leo/*）
- 絕不動 main/master/staging
- 絕不 force push
"""

# ---------------------------------------------------------------------------
# Available tools reference
# ---------------------------------------------------------------------------
_TOOL_REFERENCE = """
## 可用工具（按用途分組）

### Jira + Zendesk
- `fetch_and_summarize_ticket` — 讀取 ticket 完整內容（含 Zendesk 關聯票和 comments）

### 資料庫（唯讀）
- `mysql_query` — 查 lis_emr schema（ehr_integrations, order_clients, sftp_folder_mapping 等）

### 監控 + 日誌
- `list_sentry_issues` / `list_project_events` — 查 error 和 exception
- `search_datadog_logs` — 查 application log
- `query_general_sample_events` — 追蹤 sample 生命週期

### 審計
- `search_audit_log` — 查資料變更歷史（ClickHouse）

### 程式碼操作（Claude Code 原生）
- `Bash` — 執行 shell 命令（git, npm, etc.）
- `Read` / `Grep` / `Glob` — 讀檔案、搜尋程式碼
- `Edit` / `Write` — 修改或建立檔案

你不需要用到所有工具。根據實際情況選擇需要的。
"""

# ===========================================================================
# TICKET TRIAGE PROMPT — Goal-oriented + Self-planning + Reflection
# ===========================================================================
TICKET_TRIAGE_PROMPT = """一張新的 Jira ticket 剛被建立：**{ticket_id}**

## 你的目標
分析這張 ticket，判斷它需要什麼操作，然後執行（或給出具體建議讓使用者確認）。

## 工作方式

### Phase 1: 理解（必做）
讀取 ticket 的完整內容。讀完後，寫出你的第一次反思：
- 這張 ticket 在說什麼？
- 它需要什麼類型的工作？（程式碼修改 / DB 操作 / 排查 / 其他）
- 你需要額外查什麼才能確認？

### Phase 2: 計劃（必做）
根據 Phase 1 的理解，制定你的調查/執行計劃。不要照搬固定模板 — 根據這張 ticket 的具體情況決定：
- 需要查哪些資料來源？（DB？Sentry？Datadog？程式碼？）
- 查的順序是什麼？（哪個最可能給你關鍵資訊？先查那個）
- 預期結果是什麼？如果跟預期不符，備案是什麼？

**把計劃寫出來**，格式：
```
【計劃】
1. [第一步] — 原因：[為什麼先做這個]
2. [第二步] — 依賴：[需要第一步的什麼結果]
3. ...
預期結論方向：[根據目前理解，最可能的結論是什麼]
備案：[如果預期方向是錯的，改查什麼]
```

### Phase 3: 執行 + 反思迴圈
按計劃執行。**但計劃不是死的** — 每次拿到新資訊後，先反思再決定下一步。

如果發現：
- 原本的計劃基於錯誤假設 → 更新計劃
- 找到了非預期的線索 → 追蹤它，即使不在原始計劃裡
- 某條路查不下去 → 換方向，不要硬衝

### Phase 4: 結論
完成分析後，用以下格式整理（繁體中文）：

```
## Ticket: {ticket_id}
**類型**: [描述，不限於固定分類]
**摘要**: [一句話描述]
**信心度**: [高/中/低] — [為什麼是這個信心度]

### 分析過程
[關鍵發現的摘要，不是工具呼叫的流水帳]

### 結論
[基於分析的具體結論]

### 建議操作
[具體的下一步，按優先順序排列]

### 需要確認
[列出需要使用者判斷的決策點]

### 未解決的問題
[如果有查不到或不確定的東西，誠實列出]
```
""" + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS + _TOOL_REFERENCE

# ===========================================================================
# TRIAGE REVIEW PROMPT — Agent B independent review
# ===========================================================================
TRIAGE_REVIEW_PROMPT = """你是一個獨立的 QA 審查員。你的任務是審查另一個 AI Agent 對 Jira ticket **{ticket_id}** 的分析結果。

**核心原則：不要信任前一個 Agent 的分析。獨立驗證。**

## 前一個 Agent 的分析結果：
{agent_a_response}

## 你的目標
1. 獨立重讀 ticket，確認前一個 Agent 是否正確理解了需求
2. 驗證分析中的每個關鍵判斷
3. 找出遺漏、錯誤、或邏輯跳躍

## 工作方式
你自己決定怎麼驗證。但至少要做：
- 重新讀取 ticket 原文（用 fetch_and_summarize_ticket）
- 針對前一個 Agent 最關鍵的判斷，獨立查證（例如：它說某個 DB 記錄存在，你用 mysql_query 確認）
- 不要只看結論，注意 Agent 是否跳過了重要步驟

每次驗證後寫反思，跟前一個 Agent 的結論對比。

## 輸出格式

```
## 審查結果: {ticket_id}
**審查判定**: [通過 / 有問題 / 需要補充]

### 獨立驗證
[你自己查了什麼，發現了什麼]

### 與原始分析的差異
[哪裡一致，哪裡不一致]

### 修正建議
[如果有問題，列出具體修正項目]

### 最終結論
[綜合兩個 Agent 的分析，給出最終建議]
```
""" + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS

# ===========================================================================
# CODE REVIEW PROMPT
# ===========================================================================
TICKET_CODE_REVIEW_PROMPT = """請 review **{ticket_id}** 的 branch 上的修改。

## 你的目標
判斷這些修改是否可以 merge，或者需要修正。

## 工作方式
你自己決定怎麼 review。但你的判斷必須基於：
1. Ticket 的原始需求（用 fetch_and_summarize_ticket 讀取）
2. 實際的程式碼差異（用 Bash 跑 git diff）
3. 相關的 context（Sentry 已知問題、程式碼風格、測試覆蓋）

每看完一個面向後寫反思：這部分有沒有問題？嚴重程度？

## 輸出格式

```
## Code Review: {ticket_id}
**結論**: [可以 merge / 需要修改 / 需要討論]

### 需求符合度
[修改是否解決了 ticket 的問題]

### 問題清單
[按嚴重程度排序：blocking > warning > suggestion]

### 優點
[做得好的地方]
```
""" + _REFLECTION_PROTOCOL
