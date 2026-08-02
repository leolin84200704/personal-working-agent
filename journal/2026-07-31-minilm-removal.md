---
date: 2026-07-31
slug: minilm-removal
related: []
distilled: true
---

# 2026-07-31 — MiniLM/ChromaDB 殘骸清除（PR #17 + hotfix #18）

Related: (repo maintenance, no ticket)

## 事件軌跡

1. Leo 問「repo 裡的 all-MiniLM-L6-v2 實際會用到嗎？對中英夾雜不友善」。追使用鏈：唯一載入點 vector_store.py、唯一 importer 是手動 benchmark（4/27 後沒跑過）；每晚 dream 的 eval.py 只用 manager/scorer。README 其實早已記載退役決策與同一個 English-only 弱點 — 答案是「不會用到、可刪」。
2. PR #17：刪 vector_store + config 欄位 + test-retrieval chroma baseline + chromadb/sentence-transformers 依賴 + 87MB HF cache。
3. **Merge 後抓到自己留的雷**：config 的 field_validator 清單漏刪 `vector_store_path` → `import src.config` 炸 PydanticUserError。merge 前驗證是假陰性 — eval.py 對 config 是 lazy import，那次執行沒觸發。Hotfix PR #18 一行修掉。

## 值得記的

- **驗證要直接觸發最脆弱的點**：跑「會用到 X 的程式」不等於驗證了 X — lazy import / 條件分支會給假陰性。刪 config 欄位的正確驗證是 `import src.config` 本身，一行就好，我卻只跑了上層腳本。與 factory「Sync sibling encodings」同根（刪欄位漏衍生引用），本次無新蒸餾。
- 環境陷阱：launchd dream 用 `/usr/bin/python3`（system，有 rich），homebrew python3 沒有 — 驗 dream 相關的東西一律用 `/usr/bin/python3`。
- repo 的 README 對「為什麼退役」寫得夠好，today 的問題 30 秒就能從 README 得到方向 — 文件化決策的複利。

## Leo 原話

「這個對中英夾雜很不友善。實際上我們會用到這個model嗎？是不是沒有存在的必要？」「merged, 順便把 dream 那邊確認一下沒受影響」
