---
name: feedback-verified-means-live-not-mock
description: "Don't report \"verified/tested\" when only mock unit tests ran; verify prod-behavior claims against real data/service"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 14968cd4-2457-481b-bf50-a367273eee8b
---

報「已驗證 / verified / 真實資料」前，必須區分「邏輯驗證（mock unit test）」與「線上行為驗證（真實 DB/服務）」。涉及 prod 行為的結論，只跑 mock 不算驗證。

**Why:** VP-16850 我用 mock prisma 跑 16 個測試 pass，卻在報告寫「verified on real data」。Leo 直接問「你有實際跑過嗎？」——沒有。實際查 prod 後發現使用者看到的「空」根本不是我修的 bug，而是 `max_advance_days=28` 砍掉遠未來日期。混淆驗證層級會把錯的結論講得很有信心。

**How to apply:** 報告措辭嚴格分層——mock test pass 就說「unit logic 驗證」，別說「線上驗證」。要驗 prod 行為時，用真實連線重現（LIS-transformer-v2：`new PrismaClient({datasourceUrl: ...calendar_prod})` + require `dist/` 編譯 service 直接呼叫，read-only）。availability/查詢回空先查設定（max_advance_days、min_notice）再懷疑邏輯。見 [[feedback-batch-db-verify]]、[[feedback-test-before-push]]。
