# AI Agent 設計指南：從概念到生產級精度

> 基於實際生產環境的 AI Agent 建置經驗，總結出的通用設計原則和架構模式。
> 適用於任何需要 LLM + 工具呼叫的自動化系統。

---

## 目錄

1. [Agent 為什麼會出錯](#1-agent-為什麼會出錯)
2. [架構原則：消除資訊失真](#2-架構原則消除資訊失真)
3. [Prompt 工程：從寫死步驟到自主規劃](#3-prompt-工程從寫死步驟到自主規劃)
4. [反思協議：強制顯式推理](#4-反思協議強制顯式推理)
5. [雙 Agent 審查：消除自我確認偏差](#5-雙-agent-審查消除自我確認偏差)
6. [上下文分層載入：解決 Prompt 膨脹](#6-上下文分層載入解決-prompt-膨脹)
7. [知識管理：向量檢索與反饋評分](#7-知識管理向量檢索與反饋評分)
8. [工具整合：讓 LLM 直接操作](#8-工具整合讓-llm-直接操作)
9. [觸發與編排：Python 管 When，LLM 管 How](#9-觸發與編排python-管-whenllm-管-how)
10. [生產環境考量](#10-生產環境考量)
11. [設計決策速查表](#11-設計決策速查表)
12. [Anti-Patterns：常見錯誤](#12-anti-patterns常見錯誤)
13. [漸進式導入路線圖](#13-漸進式導入路線圖)

---

## 1. Agent 為什麼會出錯

在討論解決方案之前，必須先理解 Agent 出錯的根本原因。大部分失敗不是因為 LLM 不夠聰明，而是系統設計導致 LLM 拿不到正確的資訊、或在錯誤的約束下做決策。

### 1.1 資訊失真（Information Loss）

最常見的架構錯誤：在 LLM 和原始資料之間插入中介層。

```
❌ 典型的失真鏈：

User Message
    ↓
Intent Classifier (Python enum: BUG_FIX, FEATURE, DATABASE...)
    ↓
Skill Router (硬編碼的 if/else 決定呼叫哪個 handler)
    ↓
Handler (Python 呼叫 API → 判讀結果 → 摘要成 JSON)
    ↓
LLM 看到的是「Python 幫它整理好的摘要」
```

**兩個失真點：**

| 失真點 | 問題 | 後果 |
|--------|------|------|
| Intent Classification | Python 預先分類意圖，分錯了後面全錯 | 一步錯步步錯，model 連糾正的機會都沒有 |
| 中介層判讀 + 摘要 | Python 先解讀結果，再把「它認為重要的部分」傳給 model | Model 看到的是二手資訊，缺失的部分它無從判斷 |

**具體案例：**

```python
# ❌ Python 中介層判讀 — LLM 看不到原始資料
def check_database(customer_id):
    rows = db.query(f"SELECT * FROM integrations WHERE customer_id = {customer_id}")
    if len(rows) > 0:
        return {"status": "found", "count": len(rows)}    # LLM 只看到 count
    else:
        return {"status": "not_found"}

# ✅ 直接讓 LLM 看原始結果
def check_database(customer_id):
    rows = db.query(f"SELECT * FROM integrations WHERE customer_id = {customer_id}")
    return {"rows": rows[:20]}    # LLM 看到實際資料，自己判斷
```

差異在哪？假設 `rows` 有 3 筆但其中 2 筆的 `status = "INACTIVE"`。Python 摘要只說 "found 3 records"，LLM 會以為一切正常。但如果 LLM 看到原始資料，它能自己發現 inactive 的問題。

### 1.2 僵化分類（Rigid Classification）

```
❌ 硬編碼分類：

class TaskType(Enum):
    CODE_CHANGE = "code_change"
    DATABASE = "database"
    TROUBLESHOOT = "troubleshoot"
    UNKNOWN = "unknown"

# 問題：如果一個任務同時需要改 code + 改 DB 呢？
# 問題：如果任務類型是你沒預料到的呢？
```

**正確方式：不分類，讓 LLM 根據實際內容決定做什麼。**

分類的目的是幫助路由（「這是 A 類任務，走 A 流程」）。但如果 LLM 自己有能力決定走什麼流程，分類就是多餘的中介層。

### 1.3 自我確認偏差（Self-Confirmation Bias）

當同一個 LLM 既做分析又驗證自己的分析時，它傾向於確認自己的結論。

```
Agent 分析：「這張 ticket 需要改 repo A」
Agent 驗證：「讓我確認一下... 是的，repo A 是對的」
                                    ↑ 它不會質疑自己
```

這不是 LLM 的 bug，是所有推理系統的固有特性。人類也一樣 — 這就是為什麼 code review 要找別人來做。

### 1.4 隱式推理（Implicit Reasoning）

在 tool_use 迴圈中，LLM 看到工具結果後直接決定下一步。這個決策過程是隱式的 — 它在「想」什麼你看不到。

```
工具回傳：[3 筆 DB 記錄]
LLM 直接呼叫：下一個工具

           ↑ 它是否注意到其中 2 筆是 inactive？
             它是否考慮了其他可能性？
             它的計劃有沒有因為這個結果改變？
             → 全部不知道
```

---

## 2. 架構原則：消除資訊失真

### 2.1 核心原則：LLM 看到你看到的東西

```
✅ 正確架構：

User Message
    ↓
LLM 直接決定呼叫什麼工具
    ↓
工具執行 → 原始結果回傳（只做長度裁剪，不做解讀）
    ↓
LLM 看到原始資料 → 自己解讀 → 決定下一步
    ↓
... (迴圈，最多 N 輪)
    ↓
LLM 輸出最終結論
```

**規則：**
1. **不做 intent classification** — LLM 自己判斷意圖
2. **不做結果摘要** — 原始資料直接回傳（只在超過長度限制時裁剪）
3. **不做路由** — LLM 自己選工具、決定順序

### 2.2 中介層的唯一合法用途

中介層不是完全不能有，但只能做以下事情：

| 允許 | 不允許 |
|------|--------|
| 長度裁剪（超過 token 限制時截斷） | 解讀結果（判斷「重要/不重要」） |
| 格式轉換（XML → JSON） | 摘要（壓縮成「總結」） |
| 安全過濾（移除密碼/token） | 分類（把結果歸類） |
| 去重（完全重複的結果） | 排序（按「相關性」重排） |

**判斷標準：** 操作是否改變了語義？如果只改格式不改語義 → 可以。如果改了語義（包括省略資訊）→ 不行。

### 2.3 Tool Output 處理模板

```python
def process_tool_output(raw_output: str, max_chars: int = 50000) -> str:
    """
    處理工具輸出：只做安全裁剪，不做語義改變。
    """
    # 安全過濾
    output = redact_secrets(raw_output)

    # 長度裁剪（保留頭尾，中間截斷）
    if len(output) > max_chars:
        head = output[:max_chars // 2]
        tail = output[-max_chars // 4:]
        output = f"{head}\n\n... [截斷了 {len(raw_output) - max_chars} 字元] ...\n\n{tail}"

    return output
```

---

## 3. Prompt 工程：從寫死步驟到自主規劃

### 3.1 問題：寫死步驟的 Prompt

大多數 Agent prompt 長這樣：

```
❌ 寫死步驟：

請執行以下流程：
Step 1: 讀取任務描述
Step 2: 判斷類型（A/B/C/D）
Step 3: 如果是 A，做 1-2-3-4-5
        如果是 B，做 1-2-3
        如果是 C，做 1-2-3-4
Step 4: 輸出結果
```

**問題：**
- Model 照表操課，遇到不在表上的情況就卡住
- 不會根據實際發現調整策略
- 沒有「備案」— 第一個方向行不通就停了
- 分類框架限制了思考（「這不像 A 也不像 B，怎麼辦？」）

### 3.2 解法：Goal-Oriented + Self-Planning

```
✅ 目標導向 Prompt 結構：

## 你的目標
[一句話描述要達成什麼]

## Phase 1: 理解（必做）
讀取完整資訊。讀完後，寫出你的第一次反思：
- 這個任務在說什麼？
- 需要什麼類型的工作？
- 需要額外查什麼才能確認？

## Phase 2: 計劃（必做）
根據理解，制定調查/執行計劃。
- 需要查哪些資料？查的順序？
- 預期結論方向？
- 備案：如果預期方向錯了，改查什麼？

**把計劃寫出來。**

## Phase 3: 執行 + 反思迴圈
按計劃走。但計劃不是死的 —
- 發現計劃基於錯誤假設 → 更新計劃
- 找到非預期線索 → 追蹤它
- 某條路走不通 → 換方向

## Phase 4: 結論
[定義輸出格式，包含信心度和未解決問題]
```

### 3.3 設計原則

| 原則 | 說明 | 實踐 |
|------|------|------|
| 定義目標，不定義路徑 | 告訴 model 要去哪，不告訴它怎麼去 | 「分析這個問題」而非「先查 A 再查 B」 |
| 要求制定計劃 | 但是是 model 自己的計劃，不是你的 | 「寫出你的計劃」而非「按以下計劃執行」 |
| 要求備案 | 計劃制定時就要想失敗怎麼辦 | 「預期方向 + 備案」 |
| 允許計劃變更 | 明確告訴 model 可以改計劃 | 「計劃不是死的 — 隨時調整」 |
| 要求信心度 | 避免 model 過度自信 | 「信心度：高/中/低 — 原因」 |
| 要求列出未知 | 避免 model 假裝什麼都知道 | 「未解決的問題：...」 |

### 3.4 Prompt 模組化

當你有多個 prompt（分析、審查、code review...）時，共享的部分應該抽成模組：

```python
# 共享模組
_REFLECTION_PROTOCOL = """..."""     # 反思格式，全部 prompt 都用
_DOMAIN_CONSTRAINTS = """..."""      # 領域規則，需要的 prompt 才用
_TOOL_REFERENCE = """..."""          # 工具清單，執行型 prompt 才用

# 拼接
ANALYSIS_PROMPT = """...""" + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS + _TOOL_REFERENCE
REVIEW_PROMPT   = """...""" + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS
CODE_REVIEW_PROMPT = """...""" + _REFLECTION_PROTOCOL
```

**好處：**
- 改一個模組，全部 prompt 同步更新
- 新增 prompt 時不用重複貼規則
- 每個 prompt 只拿它需要的模組（不浪費 token）

### 3.5 Prompt 模組設計指南

| 模組類型 | 什麼時候抽出來 | 內容範例 |
|----------|---------------|---------|
| 反思協議 | 所有需要多步推理的 prompt | 反思格式、何時觸發、輸出結構 |
| 領域約束 | 涉及業務邏輯的 prompt | 關鍵業務規則、欄位映射、安全限制 |
| 工具參考 | 需要呼叫工具的 prompt | 工具清單、按用途分組、使用建議 |
| 輸出格式 | 需要結構化輸出的 prompt | 欄位定義、範例、必填/選填 |
| 角色設定 | 特定角色的 prompt（審查員等） | 角色描述、行為準則、獨立性要求 |

---

## 4. 反思協議：強制顯式推理

### 4.1 為什麼需要反思

LLM 在 tool_use 迴圈中的推理是隱式的。它看到工具結果後直接做決定。問題是：

1. **跳躍結論** — 看到第一個線索就下結論，不繼續查
2. **忽略反證** — 找到支持假設的證據就停，不看反面
3. **路徑依賴** — 一旦走上某條路就不回頭，即使發現新資訊
4. **遺忘缺口** — 查了 3 個工具後忘記還有 2 個該查的

反思協議強迫 LLM 在每次工具呼叫後暫停，明確寫出它的思考。

### 4.2 反思格式

```
【反思】
✅ 目前確認的事實：
   - [列出已經透過工具/資料確認的資訊]
   - [要具體：「查了 DB，customer_id=123 有 2 筆記錄」]

❓ 還不確定/缺少的：
   - [列出還需要查的東西]
   - [明確標注：是不知道（need to find out）還是懷疑（need to verify）]

🔄 計劃調整：
   - [原本計劃是否需要改變？為什麼？]
   - [如果不需要改，明確說「計劃不變」]

➡️ 下一步：
   - [基於以上三點，決定下一個具體動作]
```

### 4.3 何時觸發反思

| 時機 | 為什麼 |
|------|--------|
| 每次工具呼叫後 | 消化結果，避免忽略重要發現 |
| 計劃執行完一個階段後 | 回顧整體進度，調整方向 |
| 發現與預期不符的結果時 | 防止忽略反證 |
| 準備輸出最終結論前 | 最後一次檢查：有沒有遺漏？ |

### 4.4 反思的實際效果

**沒有反思：**
```
查 DB → 有記錄 → 查 Sentry → 沒 error → 結論：一切正常
                                         ↑ 但 DB 記錄的 status 是 INACTIVE
```

**有反思：**
```
查 DB → 有記錄 →
  【反思】
  ✅ 確認：customer_id=123 有 2 筆記錄
  ❓ 但注意到：其中 1 筆 status=INACTIVE，這正常嗎？
  🔄 原本計劃是直接查 Sentry，但先確認 INACTIVE 的含義
  ➡️ 下一步：查 INACTIVE 是什麼意思，是否影響功能

→ 追查 INACTIVE → 發現是根本原因 → 正確結論
```

### 4.5 反思深度調節

不是每次都需要深度反思。可以在 prompt 裡定義：

```
反思深度指引：
- 常規結果（符合預期）→ 簡短反思（2-3 句）
- 異常結果（不符合預期）→ 深度反思（完整格式）
- 階段性總結 → 完整反思 + 計劃更新
```

---

## 5. 雙 Agent 審查：消除自我確認偏差

### 5.1 原理

```
Agent A（分析者）                    Agent B（審查者）
────────────────                    ────────────────
讀取任務                            讀取 Agent A 的結論
    ↓                                   ↓
呼叫工具收集資訊                    獨立重新讀取原始任務
    ↓                                   ↓
產出分析報告                        獨立驗證關鍵判斷
    ↓                                   ↓
     └─────── 合併 ──────┘
                ↓
          最終結果
```

**關鍵設計：Agent B 只看 Agent A 的最終結論，不看推理過程。**

為什麼？如果 B 看到 A 的完整推理，B 會被 A 的敘事帶著走（anchoring bias）。B 需要形成自己的獨立判斷。

### 5.2 Agent B 的 Prompt 設計

```
你是一個獨立的審查員。

核心原則：不要信任前一個 Agent 的分析。獨立驗證。

前一個 Agent 的結論：
{agent_a_conclusion}

你的工作：
1. 獨立重新讀取原始資料
2. 驗證關鍵判斷（至少用工具查證一個關鍵事實）
3. 找出遺漏、錯誤、或邏輯跳躍

輸出：通過 / 有問題 / 需要補充
```

### 5.3 實作模式

```python
async def execute_with_review(task_id: str) -> dict:
    """雙 Agent 執行模式"""
    # Agent A: 完整分析
    result_a = run_llm(
        prompt=ANALYSIS_PROMPT.format(task_id=task_id),
        timeout=600,
    )
    agent_a_response = result_a.get("response", "")

    # Agent B: 獨立審查（只在 A 成功時執行）
    review_response = ""
    result_b = {}
    if agent_a_response and not result_a.get("error"):
        result_b = run_llm(
            prompt=REVIEW_PROMPT.format(
                task_id=task_id,
                agent_a_response=agent_a_response[:8000],  # 截斷避免 prompt 過長
            ),
            timeout=600,
        )
        review_response = result_b.get("response", "")

    # 合併結果
    combined = agent_a_response
    if review_response:
        combined += f"\n\n---\n\n## 獨立審查\n\n{review_response}"

    return {
        "response": combined,
        "agent_a": agent_a_response,
        "agent_b": review_response,
        "cost": (result_a.get("cost") or 0) + (result_b.get("cost") or 0),
    }
```

### 5.4 何時值得用雙 Agent

| 場景 | 用雙 Agent？ | 原因 |
|------|------------|------|
| 高風險決策（影響生產環境） | ✅ 值得 | 錯誤成本 > 2x token 成本 |
| 複雜分析（多步推理） | ✅ 值得 | 推理鏈越長，累積誤差越大 |
| 簡單查詢（查個狀態） | ❌ 不需要 | 單步操作不太會出錯 |
| 已有人工確認流程 | ⚠️ 視情況 | 如果人工確認可靠，雙 Agent 是浪費 |

### 5.5 成本分析

```
單 Agent:  1 次 LLM 呼叫 × 25 輪 tool use = $0.50-1.50 (取決於複雜度)
雙 Agent:  Agent A ($0.50-1.50) + Agent B ($0.20-0.50) = $0.70-2.00

Agent B 通常比 A 便宜，因為它不需要從零分析，只需要驗證關鍵點。
```

**投資回報：** 如果雙 Agent 在 10 次裡抓到 1 次錯誤，而那次錯誤的修復成本是 30 分鐘人力，那 10 次多花的 $5-7 token 費用是完全值得的。

---

## 6. 上下文分層載入：解決 Prompt 膨脹

### 6.1 問題：全量載入

```
❌ 把所有知識塞進 system prompt：

system_prompt = soul_md + memory_md + identity_md + user_md
               (~59KB, ~15,000 tokens)

問題：
- 浪費 token（大部分內容與當前任務無關）
- context window 被佔滿，留給工具結果的空間變少
- 知識越多越慢越貴
- 不可擴展（加到 200KB 就直接爆了）
```

### 6.2 解法：三層載入

```
Tier 1 — 永遠載入（~2KB）
├── 核心角色定義
├── 關鍵業務規則（不能錯的那些）
├── 安全限制
└── 指向其他知識來源的指標

Tier 2 — 按需檢索（~2-4KB）
├── 向量搜尋：用任務描述查相關知識
├── 只載入最相關的 top-N 條目
└── 透過 system prompt 追加注入

Tier 3 — 隨需讀取（按需）
├── LLM 自己決定要不要讀某個檔案
├── 透過工具呼叫（Read file）取得
└── 不佔 system prompt 空間
```

### 6.3 各層設計

#### Tier 1：核心規則（永遠存在）

**原則：只放「錯了會出大問題」的東西。**

```markdown
# 角色
你是 [角色名]，負責 [職責範圍]。

# 核心原則
1. Safety First — 理解再修改。永遠先建 branch。
2. Understand Before Act — 讀相關檔案、分析真正意圖。

# 不可違反的業務規則
[用表格列出最關鍵的映射/約束]

# 安全限制
- 允許：[具體列出]
- 禁止：[具體列出]

# 更多知識
如果需要更多 context，可以讀取以下檔案：
- MEMORY.md — 累積的經驗
- [其他知識來源]
```

**大小目標：** 1-3KB（~500-750 tokens）。如果超過 5KB，你塞太多了。

#### Tier 2：檢索知識（按相關性注入）

```python
def retrieve_context(query: str, n_results: int = 5) -> str:
    """
    從向量資料庫檢索與當前任務最相關的知識片段。
    """
    # 1. 把知識庫拆成小段（每段 = 一個主題/section）
    # 2. 用 embedding model 向量化
    # 3. 用任務描述做相似度搜尋
    # 4. 取 top-N 最相關的段落

    results = vector_store.query(query, n_results=n_results)

    sections = []
    for r in results:
        sections.append(f"### {r['title']}\n{r['text']}")

    return "\n\n".join(sections)
```

**注入方式：** 透過 system prompt 追加（`--append-system-prompt` 或 API 的 system message）。

#### Tier 3：隨需存取

不需要特別設計。只要 LLM 有讀檔案的工具（Read tool），它需要時自己會去讀。Tier 1 裡放個指標告訴它「更多知識在 MEMORY.md」就夠了。

### 6.4 什麼放在哪一層

| 內容類型 | 層級 | 原因 |
|----------|------|------|
| 角色定義 | Tier 1 | 每次都需要 |
| 不可違反的業務規則 | Tier 1 | 錯了會出大問題 |
| 安全限制 | Tier 1 | 必須永遠遵守 |
| 與當前任務相關的歷史經驗 | Tier 2 | 不一定每次都需要 |
| 相關的 code pattern | Tier 2 | 按任務檢索 |
| 曾經犯過的錯誤（gotchas） | Tier 2 | 按相似度匹配 |
| 完整的 repo 結構文件 | Tier 3 | 只在需要時讀 |
| 歷史對話紀錄 | Tier 3 | 很少需要 |
| 詳細的操作範例 | Tier 3 | 按需參考 |

### 6.5 效果對比

```
全量載入                       三層載入
─────────                      ─────────
59KB, ~15,000 tokens           Tier 1: 2KB (~500 tokens)
                               Tier 2: 2-4KB (~750 tokens)
                               Tier 3: 0 (按需)
                               ─────────────────────────
每次呼叫：15K tokens 固定成本    每次呼叫：~1.2K tokens 固定
                               + 相關知識按需載入

可擴展性：上限約 100KB          可擴展性：知識庫可無限大
                               （向量搜尋不受知識庫大小影響）
```

---

## 7. 知識管理：向量檢索與反饋評分

### 7.1 知識索引

把文件拆成小段（sections），每段是一個獨立的知識條目。

```python
def index_knowledge_file(filepath: str) -> list[dict]:
    """
    把 markdown 文件拆成 sections，每段是一個向量條目。

    拆分規則：以 ### (h3) 標題為分界。
    每個 section = 一個 document in ChromaDB。
    """
    content = Path(filepath).read_text()
    sections = []
    current_title = ""
    current_text = []

    for line in content.split("\n"):
        if line.startswith("### "):
            if current_text:
                text = "\n".join(current_text).strip()
                if len(text) > 50:  # 過濾太短的段落
                    sections.append({
                        "title": current_title,
                        "text": text,
                        "source": filepath,
                    })
            current_title = line[4:].strip()
            current_text = []
        else:
            current_text.append(line)

    return sections
```

### 7.2 反饋評分機制

用戶的反饋可以調整知識的檢索排名，不需要重新訓練模型。

```python
def update_relevance_score(document_id: str, feedback: str):
    """
    根據用戶反饋調整知識條目的檢索優先級。

    不是 RL（不改模型權重），只改 metadata。
    效果：調整哪些知識被優先檢索。
    """
    # 判斷反饋方向
    negative_keywords = ["不對", "錯了", "wrong", "incorrect", "no"]
    positive_keywords = ["好", "對", "correct", "yes", "exactly"]

    if any(kw in feedback.lower() for kw in negative_keywords):
        delta = -0.15   # 負向調整較大（確定性高）
    elif any(kw in feedback.lower() for kw in positive_keywords):
        delta = +0.05   # 正向調整較小（確定性低）
    else:
        return  # 不明確的反饋不調整

    # 更新 metadata
    current_score = get_relevance_score(document_id)  # 預設 1.0
    new_score = max(0.1, min(2.0, current_score + delta))

    collection.update(
        ids=[document_id],
        metadatas=[{"relevance_score": new_score}],
    )
```

**為什麼不對稱？**
- 用戶說「不對」→ 很明確，這條知識在這個場景下是錯的
- 用戶說「好」→ 可能只是禮貌性確認，不一定代表知識特別有價值
- 所以負向調整 (-0.15) > 正向調整 (+0.05)

### 7.3 檢索排名公式

```python
def compute_combined_score(vector_distance: float, relevance_score: float) -> float:
    """
    combined_score = semantic_similarity × relevance_score

    - vector_distance: ChromaDB 回傳的距離（越小越相似）
    - relevance_score: 從反饋累積的品質分數（預設 1.0）
    """
    semantic_similarity = 1.0 / (1.0 + vector_distance)
    return semantic_similarity * relevance_score
```

**效果：** 即使兩條知識的語義相似度相同，被多次負面反饋的那條會排更低。

### 7.4 知識庫維護

**定期清理原則：**

| 保留 | 刪除 |
|------|------|
| 領域知識（DB schema、業務規則） | 舊的對話記錄 |
| 犯過的錯誤和教訓（gotchas） | 冗餘的 metadata |
| 操作 pattern（常見修改模式） | 屬於其他文件的內容 |
| 欄位映射和預設值 | 過時的分析結果 |

**清理方法：**
1. 分類每個 section：KEEP（領域知識）vs REMOVE（噪音）
2. 刪除噪音 sections
3. 更新索引
4. 重建向量索引

---

## 8. 工具整合：讓 LLM 直接操作

### 8.1 工具設計原則

```
原則 1: 工具是 LLM 的手和眼，不是 LLM 的腦

✅ 好的工具：「讀取 DB 的 row 並回傳原始資料」
❌ 壞的工具：「讀取 DB 的 row，判斷是否異常，回傳判斷結果」

原則 2: 按用途分組，不是按技術分組

✅ 好的分組：「資料查詢」「監控日誌」「程式碼操作」
❌ 壞的分組：「REST API」「gRPC」「SQL」

原則 3: 工具描述要幫助 LLM 選擇

✅ 好的描述：「查詢 MySQL 資料庫（唯讀）。用於確認 integration 設定是否存在。」
❌ 壞的描述：「執行 SQL 查詢」
```

### 8.2 工具清單設計

在 prompt 裡列出可用工具時，按「用途」分組而不是按技術實作：

```
## 可用工具

### 任務管理
- `get_ticket` — 讀取 ticket 完整內容

### 資料查詢（唯讀）
- `query_database` — 查詢主資料庫

### 監控
- `search_errors` — 搜尋 error tracking 系統
- `search_logs` — 搜尋 application log

### 程式碼操作
- `read_file` — 讀取檔案
- `edit_file` — 修改檔案
- `search_code` — 搜尋程式碼

你不需要用到所有工具。根據實際情況選擇。
```

**「你不需要用到所有工具」** 這句話很重要 — 否則 LLM 可能覺得需要把每個工具都呼叫一遍。

### 8.3 MCP（Model Context Protocol）整合

MCP 是讓 LLM 存取外部工具的標準協議。

```json
// .mcp.json — 設定檔
{
  "mcpServers": {
    "your-tools": {
      "type": "http",
      "url": "http://your-server:8800/mcp"
    }
  }
}
```

**MCP 的價值：**
- 標準化介面 — 不需要為每個工具寫 adapter
- 動態發現 — LLM 啟動時自動取得可用工具清單
- 安全隔離 — 工具執行在 server 端，LLM 只看到結果

---

## 9. 觸發與編排：Python 管 When，LLM 管 How

### 9.1 職責分離

```
Python 的職責（編排層）              LLM 的職責（分析層）
────────────────────               ────────────────────
✅ 什麼時候觸發                     ✅ 怎麼分析
✅ 送什麼 prompt                    ✅ 呼叫什麼工具
✅ 結果存到哪裡                     ✅ 怎麼解讀結果
✅ 通知誰                           ✅ 下什麼結論
❌ 怎麼分析                         ❌ 什麼時候執行
❌ 呼叫什麼工具                     ❌ 存到哪裡
```

**Python 不做分析決策。** 它只決定 when（觸發時機）、what（哪個 prompt）、where（結果去哪）。

### 9.2 觸發模式

| 模式 | 適用場景 | 實作方式 |
|------|---------|---------|
| Webhook | 有公開 URL 的環境 | HTTP endpoint 接收事件 |
| 輪詢（Polling） | 沒有公開 URL / 開發環境 | 定時查詢 API |
| 手動觸發 | 測試 / 除錯 | API endpoint / CLI 命令 |
| 排程（Cron） | 定期報告 / 巡檢 | 定時任務 |

### 9.3 輪詢模式設計

```python
class Poller:
    """
    定時輪詢外部系統，觸發 Agent flow。
    """
    def __init__(self, interval_minutes: int = 60):
        self.interval = interval_minutes
        self.processed_ids: set[str] = set()
        self.state_file = Path("storage/poller_state.json")
        self._load_state()

    def _load_state(self):
        """從磁碟載入已處理的 ID，避免重複觸發。"""
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            self.processed_ids = set(data.get("processed", []))

    def _save_state(self):
        """儲存狀態，保留最近 500 筆（防止無限成長）。"""
        recent = list(self.processed_ids)[-500:]
        self.state_file.write_text(json.dumps({"processed": recent}))

    async def poll_once(self):
        """單次輪詢：取得新項目 → 過濾已處理 → 觸發 flow。"""
        items = await self._fetch_new_items()
        new_items = [i for i in items if i["id"] not in self.processed_ids]

        for item in new_items:
            await self._trigger_flow(item)
            self.processed_ids.add(item["id"])

        self._save_state()

    async def start(self):
        """無限迴圈，每 N 分鐘輪詢一次。"""
        while True:
            await self.poll_once()
            await asyncio.sleep(self.interval * 60)
```

**關鍵設計：**
- State persistence — 重啟不會重複處理
- 上限 500 筆 — 防止 state file 無限膨脹
- 單次 `poll_once()` 方法 — 方便測試和手動觸發

### 9.4 結果處理

```python
def save_result(task_id: str, flow_type: str, output: dict) -> Path:
    """
    儲存 flow 結果。每次執行產生一個 JSON 檔案。
    """
    filename = f"{task_id}_{flow_type}_{datetime.now():%Y%m%d_%H%M%S}.json"
    filepath = output_dir / filename
    filepath.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return filepath
```

**輸出結構建議：**

```json
{
  "flow": "task_triage_dual_review",
  "task_id": "TICKET-123",
  "timestamp": "2026-04-09T10:30:00",
  "response": "完整合併結果（Agent A + Agent B）",
  "agent_a_response": "Agent A 的原始分析",
  "agent_b_review": "Agent B 的獨立審查",
  "cost_usd": 1.24,
  "duration_ms": 45000,
  "error": null
}
```

---

## 10. 生產環境考量

### 10.1 安全

| 風險 | 緩解措施 |
|------|---------|
| LLM 執行危險命令 | 在 prompt 裡明確列出允許/禁止的操作 |
| 敏感資料洩漏 | 工具輸出過濾（redact secrets） |
| 無限迴圈 | 設定最大工具呼叫次數 + timeout |
| 修改生產環境 | DB 工具設為唯讀，寫入操作需人工確認 |

### 10.2 成本控制

```
成本公式：
  input_tokens × input_price + output_tokens × output_price

影響因素：
  - Tier 1 大小（每次都付的固定成本）
  - 工具呼叫次數（每輪都增加 token）
  - 雙 Agent（2x 但 Agent B 通常較短）
  - timeout 設定（防止跑太久）
```

**控制策略：**
1. Tier 1 越小越好（只放必要的）
2. 設 timeout（例如 10 分鐘 / 25 輪）
3. 記錄每次執行的 cost，追蹤趨勢
4. 簡單任務不用雙 Agent

### 10.3 可觀測性

每次執行應記錄：

```python
log = {
    "task_id": "...",
    "flow_type": "triage",
    "started_at": "...",
    "completed_at": "...",
    "num_turns": 15,        # 工具呼叫了幾輪
    "cost_usd": 0.94,       # 花了多少錢
    "duration_ms": 240000,   # 花了多少時間
    "agent_a_turns": 12,     # Agent A 幾輪
    "agent_b_turns": 3,      # Agent B 幾輪
    "error": None,           # 有沒有錯誤
}
```

### 10.4 錯誤處理

```python
# 三種錯誤類型：

# 1. 基礎設施錯誤（CLI 找不到、timeout）
#    → 回傳錯誤訊息，不重試
except FileNotFoundError:
    return {"error": "cli_not_found"}
except TimeoutError:
    return {"error": f"timeout_{timeout}s"}

# 2. LLM 輸出錯誤（JSON 解析失敗）
#    → fallback 到純文字
except json.JSONDecodeError:
    return {"response": raw_stdout}

# 3. 業務邏輯錯誤（Agent 判斷錯誤）
#    → 這就是雙 Agent 要抓的
#    → 透過反饋評分逐步改善
```

---

## 11. 設計決策速查表

| 決策點 | 選項 A | 選項 B | 建議 |
|--------|--------|--------|------|
| Intent Classification | Python enum 分類 | LLM 自己判斷 | **LLM 自己判斷**（除非任務極度簡單） |
| 工具結果處理 | Python 摘要 | 原始回傳 | **原始回傳**（只裁剪長度） |
| Prompt 步驟 | 寫死步驟 | 目標導向 + 自主規劃 | **自主規劃**（給目標不給路徑） |
| 推理可見性 | 隱式（直接決策） | 顯式（反思區塊） | **顯式反思**（多步任務必備） |
| 審查機制 | 自我驗證 | 獨立 Agent 審查 | **高風險用雙 Agent**，低風險單 Agent |
| Context 載入 | 全量塞入 | 分層按需 | **三層載入**（除非知識量 < 3KB） |
| 知識優化 | RL 訓練 | 反饋評分 | **反饋評分**（簡單有效，不需 GPU） |
| 觸發方式 | Webhook | 輪詢 | **看環境**（有公開 URL 用 webhook，否則輪詢） |
| 執行方式 | API SDK | CLI subprocess | **看生態**（有 MCP 支持用 CLI，否則 SDK） |

---

## 12. Anti-Patterns：常見錯誤

### 12.1 「智慧中介層」

```python
# ❌ Python 幫 LLM 判讀結果
def analyze_db_result(rows):
    if len(rows) == 0:
        return "沒有找到記錄，需要新建"    # Python 在替 LLM 思考
    elif rows[0]["status"] == "ACTIVE":
        return "記錄存在且啟用"             # 省略了其他欄位
    else:
        return "記錄存在但停用"             # LLM 看不到 WHY
```

**修正：** 直接回傳 `rows`。

### 12.2 「萬能 Prompt」

```
# ❌ 把所有場景、所有規則、所有範例塞進一個 prompt
# 結果：15,000 tokens 的 system prompt，LLM 反而抓不到重點
```

**修正：** 分層載入。核心規則 Tier 1，相關知識 Tier 2 按需檢索。

### 12.3 「假 Agent」

```python
# ❌ 看起來是 Agent，實際上每一步都是硬編碼
def process_ticket(ticket):
    step1 = llm("讀取 ticket 內容", ticket)     # 硬編碼順序
    step2 = llm("判斷類型", step1)               # 硬編碼順序
    step3 = llm("執行對應操作", step2)           # 硬編碼順序
    return step3
```

**修正：** 給 LLM 工具和目標，讓它自己決定順序。

### 12.4 「永遠照做」

```
# ❌ prompt 說「Step 1: 查 DB，Step 2: 查 Sentry，Step 3: 查 logs」
# LLM 就真的照順序全部查一遍，即使 Step 1 就找到答案了
```

**修正：** 「你不需要做所有步驟。找到答案就可以結論。」

### 12.5 「看不到的推理」

```
# ❌ LLM 呼叫了 5 個工具，中間完全沒有解釋
# 你不知道它為什麼選這些工具，也不知道它從結果中看到了什麼
# 直到最後的結論才知道它在想什麼 — 但此時要修正已經太晚了
```

**修正：** 反思協議 — 每步後寫出理解、缺口、下一步。

### 12.6 「單一 Agent 自我驗證」

```
# ❌ 同一個 Agent 分析 + 自己驗證自己
Agent: "我判斷這是 Type B"
Agent: "讓我驗證一下... 確認是 Type B" ← 當然會確認自己
```

**修正：** 高風險決策用獨立 Agent B 審查。

---

## 13. 漸進式導入路線圖

不需要一次全部實作。按以下順序漸進式導入：

### Phase 1: 基礎（1-2 天）

```
目標：消除資訊失真

□ 移除 intent classification，讓 LLM 直接選工具
□ 工具結果直接回傳（只裁剪長度，不做摘要）
□ 把業務規則整理到一個核心文件（Tier 1）
```

**驗證：** 對比修改前後，LLM 是否做出更正確的判斷。

### Phase 2: 自主規劃（1 天）

```
目標：從寫死步驟到目標導向

□ 重寫 prompt：定義目標，不定義步驟
□ 要求 LLM 自己制定計劃（Phase 2: 計劃）
□ 允許計劃變更（「計劃不是死的」）
```

**驗證：** 給一個不在預設分類裡的任務，看 Agent 能不能自己處理。

### Phase 3: 反思協議（半天）

```
目標：讓推理過程可見

□ 定義反思格式（確認/缺口/調整/下一步）
□ 在 prompt 裡注入反思協議
□ 在所有 prompt 裡用共享的反思模組
```

**驗證：** 檢查 Agent 的輸出是否包含反思區塊，是否因反思調整了方向。

### Phase 4: 上下文分層（1-2 天）

```
目標：解決 prompt 膨脹

□ 設定 Tier 1（核心規則文件，< 3KB）
□ 建立向量索引（拆分知識文件 → ChromaDB）
□ 實作 Tier 2 檢索（按任務查相關知識）
□ Tier 3 靠 LLM 自己用 Read 工具
```

**驗證：** Token 使用量是否下降？相關知識是否被正確檢索？

### Phase 5: 雙 Agent 審查（半天）

```
目標：消除自我確認偏差

□ 設計 Agent B 的 review prompt
□ 在 runner 裡串接 A → B → 合併
□ 在高風險 flow 啟用雙 Agent
```

**驗證：** Agent B 是否有抓到 Agent A 的錯誤？多花的成本是否合理？

### Phase 6: 反饋評分（1 天）

```
目標：持續改善知識品質

□ 實作反饋偵測（正面/負面 keyword）
□ 實作 relevance_score 調整
□ 在檢索排名裡加入 relevance_score
```

**驗證：** 被多次負面反饋的知識是否排名下降？

---

## 附錄 A: 完整的 Prompt 結構範例

```python
# ── 共享模組 ──

_REFLECTION_PROTOCOL = """
## 反思協議
每次呼叫工具拿到結果後，在決定下一步之前，先寫出：

【反思】
✅ 目前確認的事實：[已確認的資訊]
❓ 還不確定/缺少的：[還需要查的]
🔄 計劃調整：[是否需要改方向]
➡️ 下一步：[決定下一個動作]
"""

_DOMAIN_CONSTRAINTS = """
## 領域約束
[列出不可違反的業務規則]
"""

_TOOL_REFERENCE = """
## 可用工具（按用途分組）
[按用途分組列出可用工具]
"""

# ── 分析 Prompt ──

ANALYSIS_PROMPT = '''
## 你的目標
[一句話描述目標]

## Phase 1: 理解（必做）
[讀取完整資訊，寫出第一次反思]

## Phase 2: 計劃（必做）
[自己制定計劃，包含備案]

## Phase 3: 執行 + 反思迴圈
[按計劃執行，每步反思，可調整計劃]

## Phase 4: 結論
[定義輸出格式]
''' + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS + _TOOL_REFERENCE

# ── 審查 Prompt ──

REVIEW_PROMPT = '''
你是獨立審查員。不要信任前一個 Agent。

前一個 Agent 的結論：
{agent_a_response}

你的工作：獨立驗證。
''' + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS
```

---

## 附錄 B: 架構全景圖

```
                    ┌─────────────────────────────────────────────┐
                    │              Orchestration Layer             │
                    │                  (Python)                    │
                    │                                             │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
                    │  │ Webhook  │  │  Poller  │  │  Manual  │ │
                    │  │ Endpoint │  │ (hourly) │  │ Trigger  │ │
                    │  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
                    │       └──────────┬──┘──────────────┘       │
                    │                  ↓                          │
                    │         ┌──────────────┐                   │
                    │         │  FlowRunner  │                   │
                    │         │  (選 prompt) │                   │
                    │         └──────┬───────┘                   │
                    └────────────────┼───────────────────────────┘
                                     │
                    ┌────────────────┼───────────────────────────┐
                    │                ↓          Analysis Layer    │
                    │  ┌──────────────────────┐                  │
                    │  │      Agent A          │                  │
                    │  │  (Goal + Plan +       │                  │
                    │  │   Reflect Loop)       │                  │
                    │  └──────────┬───────────┘                  │
                    │             ↓                               │
                    │  ┌──────────────────────┐                  │
                    │  │      Agent B          │                  │
                    │  │  (Independent Review) │                  │
                    │  └──────────┬───────────┘                  │
                    └─────────────┼──────────────────────────────┘
                                  │
                    ┌─────────────┼──────────────────────────────┐
                    │             ↓          Context Layer        │
                    │                                             │
                    │  Tier 1: Core Rules (always loaded, ~2KB)  │
                    │  Tier 2: Retrieved Knowledge (on-query)    │
                    │  Tier 3: On-demand file access             │
                    │                                             │
                    └─────────────┬──────────────────────────────┘
                                  │
                    ┌─────────────┼──────────────────────────────┐
                    │             ↓          Tool Layer           │
                    │                                             │
                    │  ┌──────┐ ┌──────┐ ┌───────┐ ┌──────────┐│
                    │  │ Jira │ │  DB  │ │ Logs  │ │ Code Ops ││
                    │  └──────┘ └──────┘ └───────┘ └──────────┘│
                    │                                             │
                    └─────────────┬──────────────────────────────┘
                                  │
                    ┌─────────────┼──────────────────────────────┐
                    │             ↓          Output Layer         │
                    │                                             │
                    │  ┌──────┐ ┌───────┐ ┌──────┐ ┌──────────┐│
                    │  │ JSON │ │ Slack │ │ Jira │ │  Email   ││
                    │  │ File │ │ Msg   │ │ Cmnt │ │          ││
                    │  └──────┘ └───────┘ └──────┘ └──────────┘│
                    │                                             │
                    └─────────────────────────────────────────────┘
```

---

## 附錄 C: 效果量化

基於實際生產環境的觀察：

| 指標 | 導入前 | 導入後 | 改善 |
|------|--------|--------|------|
| 資訊失真 | Python 摘要丟失細節 | LLM 看原始資料 | 消除 |
| 分類錯誤率 | ~30%（enum 預分類） | ~5%（LLM 自判斷） | -83% |
| 推理透明度 | 不可見 | 每步有反思區塊 | 可除錯 |
| Context 大小 | 15,000 tokens/call | ~1,200 tokens/call | -92% |
| 知識可擴展性 | 上限 ~100KB | 無限制（向量搜尋） | 無上限 |
| 自我確認偏差 | 無法檢測 | Agent B 審查 | 可檢測 |

---

*Created: 2026-04-09*
*Based on: Production AI Agent development experience*
