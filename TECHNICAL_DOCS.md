# LIS Code Agent v2.0 - 技術文檔

> 完整的重構說明與技術棧介紹

---

## 目錄

1. [架構概述](#架構概述)
2. [技術棧](#技術棧)
3. [核心改進](#核心改進)
4. [代碼導覽](#代碼導覽)
5. [學習資源](#學習資源)

---

## 架構概述

### v1.0 vs v2.0

```
┌─────────────────────────────────────────────────────────────────┐
│                        v1.0 (CLI Tool)                          │
├─────────────────────────────────────────────────────────────────┤
│  CLI Command → TicketProcessor → Jira/Git → Output Report      │
│  ❌ 只能執行一次                                                 │
│  ❌ 命令行界面，需要 `ask`、`analyze` 等命令                     │
│  ❌ 記憶只是簡單 append                                         │
│  ❌ 代碼編輯是全文件替換                                         │
│  ❌ 無並發安全                                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     v2.0 (Backend Service)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  WebSocket/REST                                                  │
│       ↓                                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Agent Loop (Observe → Think → Act → Learn)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│       ↓          ↓          ↓          ↓                       │
│   Intent     RAG      Skills     Auto-Learn                   │
│  Recognition Memory                                       │
│       ↓          ↓          ↓          ↓                       │
│   Jira      Vector    Jira      Update Memory Files           │
│   Git      Store     Git        (SOUL/IDENTITY/USER/MEMORY)    │
│   Code                                                            │
│                                                                  │
│  ✅ 持續運行的服務                                               │
│  ✅ 真正對話式界面                                               │
│  ✅ 向量檢索記憶                                                 │
│  ✅ 增量代碼編輯                                                 │
│  ✅ 線程安全的 Git 操作                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 系統架構圖

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Browser    │  │  CLI Client  │  │  IDE Plugin  │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
└─────────┼─────────────────┼─────────────────┼─────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                           │ WebSocket / REST
┌─────────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  WebSocket Endpoint: /api/ws/chat                            │  │
│  │  REST Endpoints: /api/memory, /api/stats, /api/control       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent Core Layer                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Agent Loop                                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │  │
│  │  │ Observe │→│  Think  │→│   Act   │→│  Learn  │         │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │  │
│  │       ↓            ↓            ↓            ↓               │  │
│  │   Intent       RAG         Skills      Memory Update          │  │
│  │  Recognition  Search       Execution                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────┐
│                        Skills Layer                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│  │  JiraSkill   │ │  GitSkill    │ │  CodeSkill   │              │
│  └──────────────┘ └──────────────┘ └──────────────┘              │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    MemorySkill                               │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────┐
│                      Memory Layer                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Vector Store (ChromaDB)                      │  │
│  │  • conversations: 對話歷史                                    │  │
│  │  • patterns: 代碼模式                                         │  │
│  │  • gotchas: 常見陷阱                                          │  │
│  │  • code_snippets: 代碼片段                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Memory Files (Markdown)                         │  │
│  │  • SOUL.md: 核心哲學                                         │  │
│  │  • IDENTITY.md: 身份與能力                                   │  │
│  │  • USER.md: 用戶偏好                                         │  │
│  │  • MEMORY.md: 知識庫                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────────┐
│                   Integration Layer                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐   │
│  │   Jira API   │ │    Git       │ │    Claude API            │   │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 技術棧

### 後端框架

| 技術 | 版本 | 用途 | 學習資源 |
|------|------|------|----------|
| **Python** | 3.9+ | 主要語言 | [Python 官方教程](https://docs.python.org/zh-tw/3/tutorial/) |
| **FastAPI** | 0.100+ | Web 框架 | [FastAPI 官方文檔](https://fastapi.tiangolo.com/zh/) |
| **Uvicorn** | 0.23+ | ASGI 服務器 | [Uvicorn 文檔](https://www.uvicorn.org/) |
| **WebSockets** | 12.0+ | 實時通信 | [WebSocket MDN](https://developer.mozilla.org/zh-TW/docs/Web/API/WebSocket) |

### AI/ML

| 技術 | 版本 | 用途 | 學習資源 |
|------|------|------|----------|
| **Anthropic SDK** | 0.40+ | Claude API | [Anthropic Docs](https://docs.anthropic.com/) |
| **ChromaDB** | 0.4+ | 向量數據庫 | [ChromaDB Docs](https://docs.trychroma.com/) |
| **sentence-transformers** | 2.2+ | 文本嵌入 | [SBERT Docs](https://www.sbert.net/) |

### 數據處理

| 技術 | 版本 | 用途 | 學習資源 |
|------|------|------|----------|
| **Pydantic** | 2.0+ | 數據驗證 | [Pydantic Docs](https://docs.pydantic.dev/) |
| **pydantic-settings** | 2.0+ | 配置管理 | [Settings Docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |

### 外部集成

| 技術 | 版本 | 用途 | 學習資源 |
|------|------|------|----------|
| **Jira Python** | 3.8+ | Jira API | [Jira Python](https://jira.readthedocs.io/) |
| **GitPython** | 3.1+ | Git 操作 | [GitPython Docs](https://gitpython.readthedocs.io/) |

### 開發工具

| 技術 | 用途 |
|------|------|
| **pytest** | 測試框架 |
| **black** | 代碼格式化 |
| **rich** | 終端美化 |
| **aiofiles** | 異步文件操作 |

---

## 核心改進

### 1. 從 CLI 到後台服務

**v1.0 問題：**
```python
# 只能執行一次命令
python -m src.main scan
python -m src.main memory show
```

**v2.0 解決方案：**
```python
# 持續運行的服務
# src/api/main.py
app = FastAPI()

@app.on_event("startup")
async def startup():
    # 初始化向量存儲
    # 加載記憶文件
    # 準備接受連接
```

**關鍵技術點：**
- **FastAPI Lifespan**: 使用 `lifespan` 上下文管理器處理啟動/關閉
- **WebSocket**: 實現長連接對話
- **異步編程**: `async/await` 處理並發請求

### 2. Agent Loop 架構

**v1.0 問題：**
```python
# 流程是線性的，沒有學習循環
def process_ticket(ticket):
    analyze(ticket)
    create_branch()
    make_changes()
    # 過程中沒有學習
```

**v2.0 解決方案：**
```python
# src/agent/loop.py
class AgentLoop:
    async def process_message(self, message: str):
        # 1. Observe: 理解意圖
        intent = await self._observe(message)

        # 2. Think: 檢索記憶
        context = await self._think(message, intent)

        # 3. Act: 執行技能
        result = await self._act(intent, context)

        # 4. Learn: 更新記憶
        await self._learn(message, intent, result)
```

**關鍵技術點：**
- **四步循環**: Observe → Think → Act → Learn
- **意圖識別**: 使用 Claude 分析用戶意圖
- **記憶檢索**: 從向量 DB 找相關上下文

### 3. RAG (檢索增強生成)

**v1.0 問題：**
```python
# 記憶只是簡單追加，無法智能檢索
def learn_qa(question, answer):
    memory += f"\n### Q: {question}\nA: {answer}"

# 查找時需要掃描整個文件
```

**v2.0 解決方案：**
```python
# src/memory/vector_store.py
class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./storage/chroma")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def add(self, documents, metadatas):
        # 轉換成向量存儲
        embeddings = self.model.encode(documents)
        self.client.add(documents=documents, embeddings=embeddings)

    def search(self, query, n_results=5):
        # 語義搜索
        query_embedding = self.model.encode([query])
        return self.client.query(query_embeddings=query_embedding)
```

**關鍵技術點：**
- **Embeddings**: 用 `sentence-transformers` 把文本轉成向量
- **向量存儲**: ChromaDB 持久化存儲
- **語義搜索**: 根據含義而非關鍵詞搜索

### 4. 自動更新記憶

**v1.0 問題：**
```python
# 需要手動添加記憶
memory.learn_qa("問題", "答案")
```

**v2.0 解決方案：**
```python
# src/memory/auto_update.py
class MemoryAutoUpdater:
    async def extract_updates(self, conversation):
        # 用 Claude 從對話中提取學習內容
        prompt = """分析這段對話，提取需要更新的記憶..."""
        response = await self.claude.messages.create(...)
        return updates  # {"soul": [...], "identity": [...], ...}

    async def apply_updates(self, updates):
        # 自動更新 SOUL/IDENTITY/USER/MEMORY.md
        for file_type, items in updates.items():
            self._update_file(file_type, items)
```

**關鍵技術點：**
- **自動提取**: 用 Claude 識別需要記住的內容
- **結構化更新**: 按文件類型和章節組織
- **去重**: 避免重複添加相同內容

### 5. 增量代碼編輯

**v1.0 問題：**
```python
# 整個文件替換，容易破壞代碼
new_content = claude.generate(...)
file.write_text(new_content)  # 整個文件被覆蓋
```

**v2.0 解決方案：**
```python
# src/skills/code_skill.py
class CodeSkill:
    async def edit_file(self, file_path, instruction):
        current_content = file.read_text()

        # 分析代碼結構
        structure = await self._analyze_structure(current_content)

        # 要求 Claude 用 SEARCH/REPLACE 格式
        prompt = """使用 SEARCH/REPLACE 格式：
SEARCH:
<要找的代碼>
REPLACE:
<新代碼>"""

        response = await claude.messages.create(...)

        # 應用變更
        new_content = self._apply_changes(current_content, response)
```

**SEARCH/REPLACE 格式示例：**
```
SEARCH:
def old_function():
    return "old"
REPLACE:
def new_function():
    return "new"
```

### 6. 並發安全

**v1.0 問題：**
```python
# 多個請求同時操作 Git 會衝突
def process_repo(repo):
    git = GitOperator(repo)
    git.create_branch(...)  # 可能與其他請求衝突
```

**v2.0 解決方案：**
```python
# src/integrations/git_operator.py
class ThreadSafeGitOperator(GitOperator):
    _repo_locks = {}  # 每個 repo 一個鎖
    _global_lock = Lock()

    def __init__(self, repo_path):
        super().__init__(repo_path)
        with self._global_lock:
            # 獲取或創建這個 repo 的鎖
            self._lock = self._repo_locks.setdefault(repo_path, Lock())

    def create_branch(self, ...):
        with self._lock:  # 加鎖
            return super().create_branch(...)
```

**關鍵技術點：**
- **線程鎖**: 確保同一 repo 的操作串行
- **全局鎖**: 保護鎖字典本身的並發訪問

---

## 代碼導覽

### 目錄結構

```
src/
├── agent/                    # Agent 核心邏輯
│   ├── loop.py              # 主循環：Observe → Think → Act → Learn
│   ├── state.py             # 對話狀態管理
│   └── memory_bank.py       # 記憶集成 (待實現)
│
├── api/                      # Web API
│   ├── main.py              # FastAPI 應用入口
│   ├── routes/
│   │   ├── chat.py          # WebSocket 對話端點
│   │   └── control.py       # REST 控制端點
│   └── schemas.py           # Pydantic 數據模型
│
├── skills/                   # Agent 技能
│   ├── base.py              # 技能基類
│   ├── jira_skill.py        # Jira 操作
│   ├── git_skill.py         # Git 操作
│   ├── code_skill.py        # 代碼編輯
│   └── memory_skill.py      # 記憶管理
│
├── memory/                   # 記憶系統
│   ├── vector_store.py      # ChromaDB 向量存儲
│   ├── auto_update.py       # 自動更新記憶文件
│   └── manager.py           # Markdown 文件管理
│
├── integrations/             # 外部集成
│   ├── jira.py              # Jira API 客戶端
│   └── git_operator.py      # Git 操作 (含線程安全)
│
├── utils/                    # 工具函數
│   ├── logger.py            # 日誌系統
│   └── prompt.py            # Prompt 模板 (待實現)
│
└── config.py                # 配置管理
```

### 關鍵文件說明

#### 1. `src/agent/loop.py` - Agent 大腦

```python
class AgentLoop:
    async def process_message(self, message: str):
        # === OBSERVE ===
        intent = await self._observe(message)
        # Claude 分析用戶想要做什麼

        # === THINK ===
        plan = await self._think(message, intent)
        # 從向量 DB 找相關記憶

        # === ACT ===
        result = await self._act(intent, plan)
        # 執行對應的技能

        # === LEARN ===
        await self._learn(message, intent, result)
        # 更新向量 DB 和記憶文件

        return response
```

**學習重點：**
- 如何組織 AI agent 的邏輯流程
- 意圖識別的實現方式
- 上下文檢索的整合

#### 2. `src/memory/vector_store.py` - RAG 核心

```python
class VectorStore:
    def __init__(self, persist_path):
        self.client = chromadb.PersistentClient(path=persist_path)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def add(self, documents, metadatas, ids):
        # 1. 轉換成向量
        embeddings = self.model.encode(documents)
        # 2. 存入 ChromaDB
        self.client.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query, n_results=5):
        # 1. 查詢轉向量
        query_embedding = self.model.encode([query])
        # 2. 向量搜索
        results = self.client.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        return results
```

**學習重點：**
- Embeddings 是什麼，如何工作
- 向量相似度搜索原理
- ChromaDB 的基本用法

#### 3. `src/api/routes/chat.py` - WebSocket 對話

```python
@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    agent = AgentLoop()

    while True:
        # 接收用戶消息
        data = await websocket.receive_json()
        message = data["message"]

        # 處理並回應
        response = await agent.process_message(message)
        await websocket.send_json(response)
```

**學習重點：**
- WebSocket 通信協議
- FastAPI 的 WebSocket 支持
- 異步編程模式

#### 4. `src/skills/code_skill.py` - 智能代碼編輯

```python
class CodeSkill:
    async def edit_file(self, file_path, instruction):
        # 讀取當前內容
        content = file.read_text()

        # 分析結構
        structure = await self._analyze_structure(content)

        # 要求 SEARCH/REPLACE 格式
        prompt = """使用 SEARCH/REPLACE 格式..."""
        response = await self.claude.messages.create(...)

        # 應用變更
        new_content = self._apply_changes(content, response)
        file.write_text(new_content)
```

**學習重點：**
- 如何讓 AI 輸出結構化格式
- SEARCH/REPLACE 模式
- 代碼結構分析

---

## 學習資源

### FastAPI

1. **官方教程**: https://fastapi.tiangolo.com/zh/tutorial/
   - 路徑操作、請求體、響應模型
   - WebSocket 支持
   - 異步數據庫

2. **關鍵概念**:
   ```python
   from fastapi import FastAPI, WebSocket
   from pydantic import BaseModel

   app = FastAPI()

   @app.get("/")
   def read_root():
       return {"hello": "world"}

   @app.websocket("/ws")
   async def websocket_endpoint(websocket: WebSocket):
       await websocket.accept()
       while True:
           data = await websocket.receive_text()
           await websocket.send_text(f"Echo: {data}")
   ```

### Pydantic (數據驗證)

1. **官方文檔**: https://docs.pydantic.dev/

2. **關鍵概念**:
   ```python
   from pydantic import BaseModel, Field

   class User(BaseModel):
       name: str
       age: int = Field(default=0, ge=0)  # ≥ 0
       email: str | None = None  # Optional
   ```

### Anthropic Claude API

1. **官方文檔**: https://docs.anthropic.com/

2. **基本用法**:
   ```python
   from anthropic import Anthropic

   client = Anthropic(api_key="your-key")

   message = client.messages.create(
       model="claude-sonnet-4-6",
       max_tokens=1000,
       messages=[{"role": "user", "content": "Hello"}],
       system="You are a helpful assistant."
   )
   print(message.content[0].text)
   ```

### ChromaDB (向量數據庫)

1. **官方文檔**: https://docs.trychroma.com/

2. **基本用法**:
   ```python
   import chromadb

   client = chromadb.PersistentClient(path="./db")
   collection = client.get_or_create_collection("docs")

   # 添加
   collection.add(
       documents=["Hello world", "Foo bar"],
       ids=["doc1", "doc2"]
   )

   # 查詢
   results = collection.query(
       query_texts=["greeting"],
       n_results=1
   )
   ```

### sentence-transformers (文本嵌入)

1. **官方文檔**: https://www.sbert.net/

2. **基本用法**:
   ```python
   from sentence_transformers import SentenceTransformer

   model = SentenceTransformer('all-MiniLM-L6-v2')
   embeddings = model.encode(["Hello world", "Foo bar"])
   ```

### Python 異步編程

1. **Real Python**: https://realpython.com/async-io-python/

2. **關鍵概念**:
   ```python
   import asyncio

   async def fetch_data():
       await asyncio.sleep(1)  # 模擬 IO
       return "data"

   async def main():
       result = await fetch_data()
       print(result)

   asyncio.run(main())
   ```

---

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 配置環境

```bash
cp .env.example .env
# 編輯 .env 填入 API keys
```

### 3. 啟動服務

```bash
python start_agent.py
```

### 4. 測試

```bash
# 測試核心功能
python test_agent.py

# 測試 WebSocket
python test_client.py
```

---

## 常見問題

### Q: 為什麼用 WebSocket 而不是 REST？

**A**: WebSocket 提供實時雙向通信，更適合對話場景：
- 低延遲：不需要每次都建立連接
- 服務器主動推送：可以流式返回思考過程
- 持久連接：保持對話上下文

### Q: ChromaDB 和傳統數據庫有什麼不同？

**A**:
- **傳統數據庫**: 精確匹配 (`WHERE name = 'foo'`)
- **向量數據庫**: 語義搜索 (找「與 foo 相似的內容」)

### Q: 為什麼需要 `from __future__ import annotations`？

**A**: 這讓 Python 3.9+ 支持新的類型注解語法 (`str | None` 而不是 `Optional[str]`)。

### Q: Agent Loop 的四步是什麼意思？

**A**:
1. **Observe**: 理解用戶想要什麼
2. **Think**: 檢索相關記憶，制定計劃
3. **Act**: 執行操作
4. **Learn**: 從結果中學習，更新記憶

---

## 下一步

1. **閱讀代碼**: 從 `src/agent/loop.py` 開始
2. **運行測試**: `python test_agent.py`
3. **修改 prompt**: 在 `src/utils/prompt.py` 中優化
4. **添加技能**: 在 `src/skills/` 中擴展功能
5. **優化記憶**: 調整向量搜索參數

---

*文檔生成時間: 2026-04-06*
*作者: LIS Code Agent*
