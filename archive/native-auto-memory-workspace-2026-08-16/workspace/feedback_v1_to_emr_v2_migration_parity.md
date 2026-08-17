---
name: v1-java-to-emr-v2-migration-parity
description: porting v1 Java EMR-Backend behavior to lis-backend-emr-v2 必須逐欄位 enumerate Java 端寫了什麼 DB column，emr-v2 哪些路徑漏寫
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 799fca3a-9b4e-463a-ab2a-8ee00b54a461
---

從 v1 Java EMR-Backend port 任何 behavior 到 lis-backend-emr-v2 時，**必須逐欄位** enumerate Java 端 DB write 跟 emr-v2 端 DB write 對齊。「主要欄位寫了 = OK」是錯的：Java 通常在 success / fail / replay 多條路徑都寫同一組欄位，emr-v2 port 經常只 cover happy path。

**Why:** INCIDENT-2604156666 期間 Leo 發現 `hl7_file_input.julien_barcode` 跟 `sample_id_payment` 在 emr-v2 order processing 全 NULL（Java 版有）。Root cause：
- `order-finalizer.service.ts` 只在 `transactionPay` 成功路徑 set `partialResult.sample_id_payment` / `.julien_barcode`
- replay / no-stax / not-CUSTOMER_PAY / payment-fail 等路徑 — 全部漏
- Java EMR-Backend 用 `SampleService.GenerateBarcodeForSampleID` RPC（proto `sample_service.proto:54` 早就定義）拿 barcode 後**所有路徑**都寫入
- emr-v2 的 `grpc-client-v2.service.ts` 漏實作這個 wrapper method

修法見 PR #124。

**How to apply:**
- Port Java 邏輯前，先 `git grep` Java repo 的對應 `mybatis` mapper / Mapper.xml，列所有 DB UPDATE/INSERT 涉及的欄位
- 在 emr-v2 對應路徑「所有 branch」確認都寫到該欄位 — 不只 happy path
- 各 branch 對應的「來源」也要對齊：Java 從哪 RPC 拿 value，emr-v2 也要走同 RPC
- Proto 已定義但 client wrapper 沒實作的 RPC（譬如 `GenerateBarcodeForSampleID`）是常見 trap — `grep -n "rpc " *.proto` 對照 client wrapper file 看哪些有 method 哪些沒
- 寫 spec 時用 multi-branch test case（payment success / payment fail / replay）覆蓋所有路徑而非只 happy path
- 跟 Leo / PM 對齊「business 上這些路徑是否真需要寫」— 別自以為 trivial 漏掉
