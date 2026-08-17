---
name: end-to-end-equivalence-before-swap
description: 替換上游資料源 / RPC / service 前必須先驗證 end-to-end output 不變 — 不能假設「同 contract 同 service」
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 799fca3a-9b4e-463a-ab2a-8ee00b54a461
---

替換上游 data source（gRPC service、DB、API endpoint）前，必須先做 end-to-end 對照測試確認 output 完全一致；不可只看 proto / interface signature 相同就假設可互換。

**Why:** INCIDENT-2604156666 — `[INCIDENT-20260518] Use v2 gRPC as primary with v1 fallback for sample data` (c0852d0) 把 SampleTestResultService Steps 1-4 從 v1 lis package (`30276`) 切到 v2 coresamples_service (`32100`)，誤把「service migration」當「host migration」做。實際 v1 跟 v2 是**平行的兩個 service**：v1 (lis package, port 30276, Java) 跟 v2 (coresamples_service, port 32100, Go) — 不是 upgrade 關係，proto 雖然欄位名類似但 marshalling 不同（v2 Go 對 missing `sample_collection_time` 序列化為 `"0001-01-01T00:00:00Z"`、v1 Java 回實際值）。`getValidCollectionTime` validation 沒擋 year=0001 → 5/19 一夜起 14 個 EMR vendor / 約 990 個 result HL7 OBR-7 / OBR-14 = `00010101000000` push 到 vendor SFTP。

對照正確設計：**VP-16685 (e3d04f8) 是 host migration** — 每個 service 保留 port + package，只加 cloud mirror (`10.224.0.199:30276`) 跟 on-prem fallback (`192.168.60.6:30276`)，同一個 v1 lis service。

Leo: 「未來在改這種東西一定要記得 前後的 end-to-end result 絕對不能變... 非常嚴重的錯誤」「v1 就是用 v1, v2 就是用 v2 port不要改」。

**How to apply:**
- 切 RPC primary / 替換 client / 升級 service version：寫一支 read-only diff script，同一輸入打新舊兩邊、`JSON.stringify` 對比輸出。Any 欄位不一致就停下查清。proto 一樣 ≠ marshalling 一樣（string/optional/nil/zero 序列化差異）。
- 不要因為「業務不變」就 skip：欄位 marshalling、collation、time-zone、enum default、NULL 處理，跨 backend stack（Go / Java / Node）都會差。
- Production traffic 切換前至少跑 N 個 representative sample 做 diff，並 sanity-check 邊界 case（missing / null / 過去/未來日期 / 空字串）。
- 切完後第一個工作日 grep production HL7 / DB content 抽幾筆人工檢查，比對切換前同 sample。
- **辨明「host migration」vs「service migration」**：同 port + 同 package + 只換 IP 是 host migration（譬如 VP-16685 cloud mirror）— 安全。換 port / 換 package / 換 backend language 是 service migration — 屬於不同 service 不是 upgrade，要把它當全新 integration 看，跑完整 contract 測試。
- **辨明 v1 / v2 是平行還是 upgrade 關係**：lis-backend-emr-v2 內 v1 (`lis` package, port 30276) 跟 v2 (`coresamples_service` package, port 32100) 是**平行**的，不是「v2 取代 v1」。各 caller 各有設計用途；不要看到 v2 就以為該全切過去。動之前看 git blame 確認原作者意圖。
