# LIS Code Agent - Tool Use 架構改造技術文件

> 改造目標：達到 Claude Code 等級的「單次決策精確度」

---

## 1. 問題診斷：為什麼舊架構精度不夠

### 舊架構的資訊流

```
User Message
    │
    ▼
Intent Classifier (Python enum: EMR_INTEGRATION, DATABASE, GIT...)
    │
    ▼
Skill Loader (讀 SKILL.md → 產生 structured plan)
    │
    ▼
Skill Executor (Python 呼叫工具 → 判讀結果 → 封裝成摘要 JSON)
    │
    ▼
LLM 看到的是「Python 幫它整理好的摘要」，不是原始資料
```

**兩個資訊失真點：**

1. **Intent Classification 瓶頸** — Python enum 預先分類意圖，分錯了後面全錯
2. **Skill 中介層的判讀+摘要** — Python 先解讀工具回傳，再把「它認為重要的部分」傳給 model。Model 看到的是二手資訊

### Claude Code 的資訊流（目標）

```
User Message
    │
    ▼
LLM 直接決定呼叫哪些 tools（無 intent classification）
    │
    ▼
Tool 執行 → 回傳原始資料（只裁切長度，不判讀）
    │
    ▼
LLM 自己解讀原始資料 → 決定下一步
```

**零資訊失真** — model 拿到的跟你在 terminal 看到的一樣。

---

## 2. 核心改動：移除中介層

### 2.1 移除 Intent Classification

**刪掉的：** `IntentType` enum、`_classify_intent()` 函式、所有 intent routing 邏輯

**取代方式：** Claude 的 `tool_use` API 讓 model 自行決定要呼叫哪些工具。System prompt 提供領域知識，model 根據知識 + 使用者訊息直接選擇工具。

```python
# 舊: Python 先分類
intent = classify_intent(user_message)  # → EMR_INTEGRATION
skill = load_skill(intent)              # → 載入對應 SKILL.md
result = execute_skill(skill, ticket)    # → Python 驅動流程

# 新: Model 直接決定
response = claude.messages.create(
    model="claude-sonnet-4-6",
    tools=TOOL_DEFINITIONS,       # 16 個工具的 schema
    messages=api_messages,         # 含對話歷史
    system=system_prompt,          # 含領域知識
)
# response.content 裡會有 tool_use blocks，由 model 自己選的
```

### 2.2 工具回傳改為「裁切+格式化」

**核心原則：Python 只做 execute + trim，不做 interpret + summarize**

| 工具 | 舊回傳（摘要） | 新回傳（原始） |
|------|----------------|----------------|
| read_file | `{"summary": "Config file with 3 DB entries"}` | `cat -n` 格式的原始內容（含行號） |
| jira_get_ticket | `{"key_info": "EMR ticket for provider 12345"}` | 完整 ticket JSON（所有欄位） |
| grep | `{"matches": 3, "summary": "Found in 3 files"}` | 完整 matching lines + 檔案路徑 + 行號 |
| git_diff | `{"changed_files": 2, "summary": "..."}` | raw diff 輸出（跟 terminal 一樣） |
| run_bash | `{"status": "success", "output_summary": "..."}` | stdout + stderr + exit code |

**裁切策略（Safety-net truncation）：**

```python
MAX_OUTPUT_CHARS = 80_000   # ~20K tokens，安全上限
MAX_FILE_LINES = 500        # 單次最多讀 500 行
MAX_SEARCH_RESULTS = 50     # 搜尋最多 50 筆

def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... (truncated, showing {limit} of {len(text)} chars)"
```

**重點：model 控制查詢精度，Python 只負責最後的安全裁切。**

例如 model 可以：
- 先 `git_diff --stat` 看概覽 → 再 `git_diff -- src/specific_file.ts` 看細節
- 先 `read_file(offset=1, limit=50)` 看開頭 → 再 `read_file(offset=200, limit=50)` 跳到特定區段
- 先 `grep("customer_id")` 粗搜 → 再 `read_file` 精讀特定檔案

---

## 3. Tool Use 迴圈機制

### 3.1 完整迴圈流程

```
User Message
    │
    ▼
┌─────────────────────────────────────────────┐
│            process_message()                │
│                                             │
│  1. 加入對話歷史                             │
│  2. 建構 system prompt（三層式載入）          │
│  3. 進入 tool_use 迴圈（最多 25 輪）：       │
│                                             │
│     ┌──────────────────────────────┐        │
│     │  Claude API call             │        │
│     │  - system: 領域知識          │        │
│     │  - tools: 16 個工具定義      │        │
│     │  - messages: 對話歷史        │        │
│     └──────────┬───────────────────┘        │
│                │                            │
│         ┌──────┴──────┐                     │
│         │             │                     │
│    tool_use?     text only?                 │
│         │             │                     │
│         ▼             ▼                     │
│    Execute tools   Return response          │
│    Append results  (迴圈結束)               │
│    Continue loop                            │
│         │                                   │
│         └──────→ Next round                 │
│                                             │
│  4. 學習：儲存對話 + 更新 feedback scores    │
└─────────────────────────────────────────────┘
```

### 3.2 關鍵程式碼（`src/agent/loop.py`）

```python
async def process_message(self, message: str) -> dict:
    self.context.add_message("user", message)
    api_messages = self._build_api_messages()
    system_prompt = self._build_system_prompt(user_message=message)

    for round_num in range(MAX_TOOL_ROUNDS):  # MAX = 25
        response = self.claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=api_messages,
        )

        # 分離 text 和 tool_use blocks
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # 無 tool_use → 最終回應
        if not tool_uses:
            return {"response": "\n".join(text_parts), ...}

        # 有 tool_use → 執行並送回結果
        api_messages.append({"role": "assistant", "content": [...]})

        tool_results = []
        for tool_use in tool_uses:
            result = execute_tool(tool_use.name, tool_use.input)  # 原始回傳
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            })

        api_messages.append({"role": "user", "content": tool_results})
        # → 下一輪，model 看到原始結果後自己決定下一步
```

### 3.3 為什麼限制 25 輪

- 正常的 EMR integration 任務大約需要 5-10 輪 tool 呼叫
- 複雜任務（多 repo、多 DB 查詢）可能到 15-20 輪
- 25 是防止無限迴圈的安全上限
- 超過 25 輪會回傳已有的 text + warning

---

## 4. 三層式上下文載入（Tiered Context Loading）

### 4.1 問題

舊設計把 SOUL.md + MEMORY.md + IDENTITY.md + USER.md 全部塞進 system prompt。隨著 MEMORY.md 內容累積（目前 55 sections），prompt 已膨脹到 ~59KB（~15K tokens），造成：

- **注意力稀釋** — model 要在大量無關資訊中找到需要的規則
- **成本浪費** — 每次 API call 都傳送大量不需要的 context
- **精度下降** — 知識越多，prompt 越長，精度反而越差

### 4.2 三層架構

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: Always Loaded (~7.5KB, ~1,873 tokens)              │
│                                                             │
│ SOUL_CORE.md  - 核心規則（安全原則、EMR mapping、Git 規範） │
│ IDENTITY.md   - Agent 身份                                  │
│ USER.md       - 使用者偏好                                  │
│                                                             │
│ → 每次 API call 都載入                                      │
├─────────────────────────────────────────────────────────────┤
│ Tier 2: Retrieved (~2-4KB, based on user message)          │
│                                                             │
│ ChromaDB 向量搜尋 → 取回跟當前問題最相關的 5 個段落         │
│ 來源: MEMORY.md sections + SOUL.md detailed sections       │
│ 排序: combined_score = (1/(1+distance)) * relevance_score  │
│ 預算: TIER2_BUDGET = 8,000 chars                            │
│                                                             │
│ → 只在有 user message 時載入                                │
├─────────────────────────────────────────────────────────────┤
│ Tier 3: On-demand (model pulls when needed)                │
│                                                             │
│ memory_search tool — model 自己決定何時搜尋                 │
│ 搜尋 conversations, patterns, gotchas, code_snippets       │
│                                                             │
│ → model 覺得 Tier 1+2 不夠時才會主動呼叫                   │
└─────────────────────────────────────────────────────────────┘
```

**實際效果：**

| 指標 | 舊設計 | 新設計 |
|------|--------|--------|
| System prompt 大小 | ~59KB (~15K tokens) | ~8-12KB (~2-3K tokens) |
| 每次都載入的無關知識 | 全部 MEMORY.md | 只有核心規則 |
| 跟當前問題相關的知識 | 混在一堆無關內容中 | 被 vector search 挑出放在最前面 |

### 4.3 SOUL_CORE.md — 什麼該放 Tier 1

只放**每次都需要**的規則：

- Core Principles（安全原則、理解再行動）
- Branch Naming（feature/leo/*, bugfix/leo/*）
- Git Safety（哪些能做、哪些不能做）
- **EMR Identity Mapping**（最關鍵的業務規則 — Provider ID vs Practice ID）
- Decision Framework（遇到不確定的怎麼辦）
- Communication Style（繁中、簡潔）

**不放 Tier 1 的：** 具體範例、歷史 gotchas、特定 repo 的設定細節、DB schema 細節 — 這些放 Tier 2 按需取用。

### 4.4 ChromaDB 索引（`src/memory/indexer.py`）

**索引流程：**

```python
# 第一次收到訊息時自動觸發
def _ensure_knowledge_indexed(self) -> None:
    collection = self.vector_store.client.get_or_create_collection(name="knowledge")
    if collection.count() == 0:
        n1 = index_memory_file(self.vector_store)   # 解析 MEMORY.md → 55 sections
        n2 = index_soul_details(self.vector_store)   # 解析 SOUL.md → 14 sections
```

**解析方式：** 按 `### header` 分割 markdown，每段存成一筆 ChromaDB document，metadata 包含：

```python
{
    "source": "MEMORY.md",           # 來源檔案
    "title": "ID Mapping for EMR",   # 段落標題
    "parent": "EMR Integration",     # 上層 ## header
    "relevance_score": 1.0,          # 初始分數，會被 feedback 調整
}
```

**檢索排序公式：**

```
combined_score = (1 / (1 + vector_distance)) * relevance_score
```

- `vector_distance` — ChromaDB 向量相似度距離（越小越相似）
- `relevance_score` — metadata 裡的權重（0.1 ~ 2.0），被 feedback 機制動態調整
- 兩者相乘 = 越相似且越被用戶認可的段落排越前面

---

## 5. Feedback Scoring 機制（越用越準）

### 5.1 原理

不做 RL 訓練（那是 model 層的事，需要開源模型 + GPU）。
改用**檢索權重調整**：偵測使用者的修正/接受 → 調整 ChromaDB 裡的 `relevance_score` → 下次檢索時相關知識排序改變。

```
使用者說「不對」或「錯了」
    │
    ▼
找出上一輪載入的知識段落（用上一個 user message 做 vector search）
    │
    ▼
relevance_score -= 0.15（這些知識對那個問題沒幫助）
    │
    ▼
下次類似問題 → 這些段落排名降低 → 其他段落有機會被選中
```

```
使用者說「好」或「ok」或「對」
    │
    ▼
relevance_score += 0.05（這些知識有用）
    │
    ▼
下次類似問題 → 這些段落排名提升
```

### 5.2 為什麼正面調整比負面小

- **負面 = -0.15**：使用者明確說「錯了」，知識的傷害較確定
- **正面 = +0.05**：使用者說「ok」可能只是在確認，不一定是因為知識特別好
- **不對稱調整**避免「所有知識分數都膨脹」的問題
- 分數範圍限制在 `[0.1, 2.0]`：不會歸零（可能未來有用），也不會無限膨脹

### 5.3 偵測邏輯

```python
# 負面訊號（使用者在修正 agent）
negative_patterns = [
    "不對", "不是", "錯了", "no,", "no ", "wrong", "incorrect",
    "不要", "別這樣", "重做", "再試", "redo", "try again",
]

# 正面訊號（使用者接受並繼續）
positive_patterns = [
    "好", "ok", "對", "correct", "沒錯", "繼續", "下一步",
    "執行", "proceed", "確認", "就這樣",
]
```

**觸發條件：** 至少要有 3 則歷史訊息（至少經過一輪 agent 回覆後的反饋才有意義）。

### 5.4 與 RL 的差異

| 面向 | RL 訓練 (OpenClaw-RL) | Feedback Scoring (LIS Agent) |
|------|----------------------|------------------------------|
| 調整對象 | Model 權重 | 知識檢索排名 |
| 需要的資源 | 開源模型 + GPU + 訓練框架 | 只需 ChromaDB metadata |
| 效果範圍 | 改變 model 對所有 input 的行為 | 只改變哪些知識被優先取用 |
| 適用場景 | 自建 model 團隊 | 使用 Claude API 的 agent |
| 累積效果 | 指數級（model 本身變強） | 線性（檢索越來越準） |

---

## 6. 工具定義清單

16 個工具，全部在 `src/tools/definitions.py` 定義：

### Jira 工具
| 工具 | 用途 | 必要參數 |
|------|------|----------|
| `jira_get_ticket` | 取得單張 ticket 完整資料 | `ticket_id` |
| `jira_get_assigned` | 取得分配給我的 tickets | (optional: `status`, `project`, `limit`) |
| `jira_search` | 搜尋 tickets | `query` |

### 檔案工具
| 工具 | 用途 | 必要參數 |
|------|------|----------|
| `read_file` | 讀取檔案（含行號） | `path` (optional: `offset`, `limit`) |
| `edit_file` | 精確字串取代 | `path`, `old_string`, `new_string` |
| `write_file` | 建立/覆寫檔案 | `path`, `content` |

### 搜尋工具
| 工具 | 用途 | 必要參數 |
|------|------|----------|
| `search_files` | Glob 搜尋檔案名 | `pattern` |
| `grep` | Regex 搜尋檔案內容 | `pattern` |

### 執行工具
| 工具 | 用途 | 必要參數 |
|------|------|----------|
| `run_bash` | 執行任意 bash 指令 | `command` |

### Git 工具
| 工具 | 用途 | 必要參數 |
|------|------|----------|
| `git_status` | 查看 repo 狀態 | `repo` |
| `git_diff` | 查看差異 | `repo` |
| `git_log` | 查看 commit 歷史 | `repo` |
| `git_create_branch` | 建立分支 | `repo`, `branch_name`, `ticket_id` |
| `git_commit` | 提交變更 | `repo`, `message` |
| `git_push` | 推送到 remote | `repo` |

### 記憶工具
| 工具 | 用途 | 必要參數 |
|------|------|----------|
| `memory_search` | 向量語意搜尋知識庫 | `query` |

---

## 7. 安全機制

### 7.1 工具層安全

```python
# 危險指令封鎖
BLOCKED_PATTERNS = ["rm -rf /", "rm -rf ~", "mkfs.", "> /dev/sd"]

# 輸出截斷
MAX_OUTPUT_CHARS = 80_000
MAX_FILE_LINES = 500
MAX_SEARCH_RESULTS = 50
```

### 7.2 Git 安全（保留原有的 GitOperator）

```
ALLOWED_PREFIXES = ["feature/leo/", "bugfix/leo/"]
PROTECTED_BRANCHES = ["main", "master", "develop"]
BLOCKED_COMMANDS = ["push --force", "reset --hard"]
```

### 7.3 迴圈安全

```python
MAX_TOOL_ROUNDS = 25  # 防止無限迴圈
```

---

## 8. 實際操作

### 8.1 檔案結構

```
src/
├── tools/
│   ├── __init__.py          # exports TOOL_DEFINITIONS, execute_tool
│   ├── definitions.py       # 16 個工具的 JSON Schema 定義
│   └── executors.py         # 工具執行函式（回傳原始字串）
├── agent/
│   ├── loop.py              # AgentLoop: tool_use 迴圈 + 三層式載入 + feedback
│   └── state.py             # ConversationContext: 簡化的對話狀態
├── memory/
│   ├── indexer.py            # MD → ChromaDB 索引 + 檢索 + score 更新
│   ├── vector_store.py       # ChromaDB wrapper
│   └── manager.py            # 讀取 MD 檔案
├── api/
│   ├── routes/chat.py        # WebSocket 即時串流 tool events
│   └── schemas.py            # API 資料模型
└── config.py                 # 設定（含 ChromaDB 路徑）

SOUL_CORE.md                  # Tier 1 核心規則（~1.5KB）
SOUL.md                       # 完整規則（Tier 2 詳細段落的來源）
MEMORY.md                     # 累積知識（Tier 2 段落的來源）
IDENTITY.md                   # Agent 身份
USER.md                       # 使用者偏好
```

### 8.2 新增知識

**手動新增 MEMORY.md 段落後，需要重新索引 ChromaDB：**

```python
# 方法 1: 刪除 ChromaDB 資料，下次對話時自動重新索引
# ChromaDB 預設路徑: settings.chroma_path

# 方法 2: 程式碼內手動觸發
from src.memory.indexer import index_memory_file, index_soul_details
from src.memory.vector_store import VectorStore
from src.config import get_settings

settings = get_settings()
vs = VectorStore(persist_path=str(settings.chroma_path))
index_memory_file(vs)      # 會先清除舊的再重新索引
index_soul_details(vs)
```

### 8.3 調整 Tier 1 核心規則

**編輯 `SOUL_CORE.md`** — 這裡的內容每次 API call 都會載入，所以：

- 只放「每次都需要」的規則
- 控制在 ~2KB 以內（~500 tokens）
- 新增業務規則時先想：這是每次都需要，還是按需取用？
  - 每次都需要 → SOUL_CORE.md
  - 按需取用 → MEMORY.md 或 SOUL.md（會被 Tier 2 檢索）

### 8.4 監控 Feedback Scoring 效果

```python
# 查看某個知識段落的當前 relevance_score
from src.memory.vector_store import VectorStore
from src.config import get_settings

settings = get_settings()
vs = VectorStore(persist_path=str(settings.chroma_path))
collection = vs.client.get_collection("knowledge")

# 查看所有段落的 scores
all_data = collection.get(include=["metadatas"])
for id_, meta in zip(all_data["ids"], all_data["metadatas"]):
    score = meta.get("relevance_score", 1.0)
    if score != 1.0:  # 只顯示被調整過的
        print(f"  {id_}: {meta['title']} → score={score}")
```

### 8.5 WebSocket 即時串流

前端接收的事件格式：

```json
// Tool 開始執行
{"type": "tool_use", "tool": "jira_get_ticket", "input": {"ticket_id": "VP-15979"}}

// Tool 執行結果預覽
{"type": "tool_result", "tool": "jira_get_ticket", "result_preview": "...前 500 字..."}

// 最終回應
{"type": "response", "content": "根據 VP-15979...", "tool_calls": [...], "rounds": 3}
```

---

## 9. Flow 工作流程系統

### 9.1 設計原則

Flow 是「工作流程編排」，不是「分析流程」：

```
Flow（Python 負責）：什麼時候啟動、用哪個 prompt、結果送去哪
分析（LLM 負責）：  ticket 是什麼類型、該改哪個 repo、怎麼改
```

**跟舊架構的關鍵差異：** 舊的 pipeline 用 Python if-else 決定「資料怎麼解讀」。
新的 flow 用 Python 只決定「什麼事件觸發什麼 prompt」，所有判斷由 LLM 完成。

### 9.2 架構（Dual-Agent Review）

```
External Event          Flow Layer                    Agent A              Agent B
─────────────          ──────────                    ─────────            ─────────

Jira Webhook ──→ FlowRunner ──→ claude -p (Triage) ──→ 分析結果 ──→ claude -p (Review)
  (ticket created)  (選 prompt)   (讀 ticket, 查工具)     │         (獨立重新驗證)
                        │                                  │              │
Manual Trigger ─────────┘                                  ▼              ▼
  (curl / API)                                      Agent A 報告    Agent B 審查
                                                           │              │
                                                           └──── 合併 ────┘
                                                                  │
                                                                  ▼
                                                           儲存 + 通知
                                                         (Jira / Slack / JSON)
```

**為什麼需要 Dual-Agent？**
- Agent A 可能有 self-confirmation bias（自己的分析傾向認為自己是對的）
- Agent B 獨立重讀 ticket，不看 Agent A 的推理過程，只看最終結論
- 這等同於 code review：一個人寫、另一個人審

### 9.3 Prompt 設計原則

**舊設計（v1）— 寫死步驟：**
```
Step 1: 讀取 Ticket
Step 2: 判斷類型 (A/B/C/D)
Step 3: 根據類型照表操課
```
問題：遇到非預期情況（ticket 同時是 A+B、資訊不完整、需要追蹤新線索），model 不知道怎麼辦。

**新設計（v2）— Goal + Plan + Reflect：**
```
Phase 1: 理解 — 讀 ticket，寫出第一次反思
Phase 2: 計劃 — 自己拆解任務（不照模板），寫出計劃和備案
Phase 3: 執行 + 反思迴圈 — 每步之後強制寫出：
         ✅ 目前確認的事實
         ❓ 還不確定/缺少的
         🔄 計劃是否需要調整
         ➡️ 下一步
Phase 4: 結論 — 包含信心度和未解決問題
```

**關鍵差異：**
| 面向 | v1 | v2 |
|------|----|----|
| 步驟 | 寫死 Step 1-2-3 | Model 自己制定計劃 |
| 分類 | 固定 A/B/C/D | 不限於固定分類 |
| 反思 | 無（隱式推理） | 每步強制寫出反思區塊 |
| 計劃調整 | 不會 | 發現新資訊時更新計劃 |
| 備案 | 無 | 制定計劃時就要想備案 |
| 信心度 | 無 | 輸出包含信心度 + 原因 |

### 9.4 Prompt 共享模組

`src/flows/prompts.py` 使用模組化拼接：

```python
TICKET_TRIAGE_PROMPT = """...""" + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS + _TOOL_REFERENCE
TRIAGE_REVIEW_PROMPT  = """...""" + _REFLECTION_PROTOCOL + _DOMAIN_CONSTRAINTS
TICKET_CODE_REVIEW_PROMPT = """...""" + _REFLECTION_PROTOCOL
```

| 模組 | 內容 | 誰用 |
|------|------|------|
| `_REFLECTION_PROTOCOL` | 反思格式和規則 | 全部 |
| `_DOMAIN_CONSTRAINTS` | EMR 業務規則、Git 安全 | Triage + Review |
| `_TOOL_REFERENCE` | 可用工具按用途分組 | 只有 Triage |

### 9.5 Ticket Triage Flow（自動分流 + 審查）

**觸發：** Jira ticket 被建立 → webhook/polling → `FlowRunner.on_ticket_created()`

**Agent A — 分析（`TICKET_TRIAGE_PROMPT`）：**
- 自己理解 ticket → 制定計劃 → 執行 + 反思迴圈 → 產出結論
- 不限於固定類型，根據實際內容決定需要做什麼
- 每個 tool call 後寫反思（確認/缺口/調整/下一步）

**Agent B — 審查（`TRIAGE_REVIEW_PROMPT`）：**
- 獨立重讀 ticket，自己決定怎麼驗證
- 比對 Agent A 的關鍵判斷，獨立查證
- 輸出：通過 / 有問題 / 需要補充

**Python 只決定 WHEN 和 WHERE。** Model 自己決定 HOW。

### 9.6 API Endpoints

| Method | Path | 用途 |
|--------|------|------|
| POST | `/api/webhook/jira` | 接收 Jira webhook（ticket created 事件） |
| POST | `/api/webhook/trigger` | 手動觸發 flow（測試用） |
| GET | `/api/webhook/status/{ticket_id}` | 查詢 flow 執行狀態和結果 |

### 9.7 使用方式

**測試 triage flow（不需要 Jira webhook）：**

```bash
# 手動觸發
curl -X POST http://localhost:8000/api/webhook/trigger \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": "VP-16000", "flow": "triage"}'

# 查詢結果（flow 在背景執行，需等幾秒）
curl http://localhost:8000/api/webhook/status/VP-16000
```

**設定 Jira Webhook：**

1. Jira Admin → System → WebHooks → Create a WebHook
2. URL: `https://your-server/api/webhook/jira`
3. Events: Issue → created
4. （可選）設定 Secret → 填入 `.env` 的 `JIRA_WEBHOOK_SECRET`

**啟用通知：**

```bash
# .env
FLOW_POST_TO_JIRA=true              # 分析結果自動寫回 Jira comment
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx  # Slack 通知
```

### 9.8 新增 Flow

在 `src/flows/prompts.py` 加新的 prompt template，在 `src/flows/runner.py` 加新的 method：

```python
# prompts.py
DEPLOYMENT_CHECK_PROMPT = """請檢查 {repo} 的 {branch} 是否可以部署：
1. git_diff staging..{branch} 看差異
2. 確認沒有遺漏的檔案
3. 確認測試通過
"""

# runner.py
async def on_deployment_check(self, repo: str, branch: str) -> dict:
    agent = AgentLoop(session_id=f"flow_deploy_{repo}")
    prompt = DEPLOYMENT_CHECK_PROMPT.format(repo=repo, branch=branch)
    return await agent.process_message(prompt)
```

**重點：新增 flow 只需要寫 prompt。不需要寫任何分析邏輯。**

### 9.9 檔案結構

```
src/flows/
├── __init__.py     # exports FlowRunner, prompts
├── prompts.py      # Prompt templates（LLM 看的指令）
└── runner.py       # FlowRunner（編排：觸發 → prompt → 通知）

src/api/routes/
└── webhook.py      # Webhook endpoints（入口）
```

---

## 10. 對比總覽

```
舊架構                          新架構
────────────────────            ────────────────────
Intent Classification           Model 直接選工具
        ↓                              ↓
Python Skill 判讀+摘要           Python 只 execute + trim
        ↓                              ↓
Model 看到二手資訊               Model 看到原始資料
        ↓                              ↓
全部 MD 塞 system prompt        三層式載入（7.5KB → 按需）
(59KB, ~15K tokens)             (8-12KB, ~2-3K tokens)
        ↓                              ↓
無學習機制                       Feedback scoring
                                (偵測修正 → 調整檢索排名)
        ↓                              ↓
Single Agent                    Dual-Agent Review
(self-confirmation bias)        (Agent A 分析 → Agent B 獨立審查)
```

---

*Created: 2026-04-09*
*Based on: Claude Code architecture analysis + LIS Agent v2 implementation*
