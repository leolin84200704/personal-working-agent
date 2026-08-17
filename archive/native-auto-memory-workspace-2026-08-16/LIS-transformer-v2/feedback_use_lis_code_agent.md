---
name: Always use lis-code-agent knowledge first
description: Must read lis-code-agent knowledge files before attempting gRPC, data migration, or infrastructure tasks
type: feedback
originSessionId: 378416c3-b999-420c-89bb-7c862dff25ce
---
遇到 gRPC、data migration、或任何基礎設施相關任務時，必須先讀 `/Users/hung.l/src/lis-code-agent/knowledge/` 目錄的知識檔案。

**Why:** 2026-04-20 更新 v2_calendar patient calendar 時，沒有先查 lis-code-agent knowledge，導致：
1. 錯誤使用 crm.contacts（不完整資料源）而非 gRPC GetCustomer（權威資料源）
2. 從 .env 猜 gRPC endpoint 猜錯（試了 10.224.0.53:8084、192.168.60.6:30278），正確答案 192.168.60.6:30276 早已記載在 `emr-integration.md`
3. 浪費大量時間反覆嘗試錯誤方案

**How to apply:**
1. 任何涉及 gRPC、customer 資料、EMR integration 的任務 → 先讀 `emr-integration.md`
2. 任何涉及 build/deploy/config 的任務 → 先讀 `patterns.md`
3. 不確定時 → 用 Grep 搜尋整個 knowledge 目錄
4. 知識庫路徑: `/Users/hung.l/src/lis-code-agent/knowledge/`
