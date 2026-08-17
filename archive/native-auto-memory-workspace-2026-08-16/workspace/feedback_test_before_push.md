---
name: test-before-push
description: prod-impacting branch push 前必須跑 unit test 並驗證新 behavior，不只 npm run build；compile pass ≠ behavior correct
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 37705de5-a5b9-4549-b1be-2b522e1b4b48
---

# 規則

**任何要 push 進 lis-backend-emr-v2（會 Jenkins auto-deploy prod）的 code change**，push 前必須：

1. `npm run build` 過（compile-level）
2. **跑相關 unit test**（behavioral level）— 用 `npx jest --testPathPatterns="<related-pattern>"`
3. 如果引入新 logic 分支（new catch block / new method / new condition），**寫對應的 unit test 涵蓋每個分支**
4. 對 prod-impacting change，建議先 push 到 non-deploy branch / 開 draft PR 跑 CI 觀察

只跑 build = 只驗證 TypeScript syntax，**不驗證程式行為**。Leo 已多次糾正類似情況（[[start_dev_iron_rule]] 是 build 必須過；本條延伸 = build 過了還不夠）。

## Why

INCIDENT-20260601 我寫 SFTP post-timeout verify patch，63 行新 logic 涵蓋 5+ 個分支：
- timeout + verify enabled + reconnect + stat success matching size → SUCCESS
- timeout + verify enabled + stat returns mismatched size → ERROR
- timeout + verify enabled + stat fails → ERROR
- non-timeout error → skip verify
- verify disabled by kill switch → skip verify
- stat itself times out → ERROR

我只跑 `npm run build` 過就直接 push 到 deploy branch。Leo 問「你有做過 end-to-end test 和 unit test 嗎」我才意識到。

事後補 6 個 spec test（per-branch coverage），結果 24/24 pass。沒問題是運氣好——分支邏輯有可能因為 closure scope / async ordering bug 而錯誤。

## How to apply (pre-push checklist)

```
□ npm run build 過
□ git diff 看新 logic 的所有 if / try-catch / 分支條件
□ 對應 spec file 存在嗎？
  - 是：npx jest --testPathPatterns=<spec> 跑現有，pass 才繼續
  - 否：考慮為新 logic 加 spec（最少涵蓋 main happy path + 1 個 error path）
□ 新增的 if / branch 都有 test 覆蓋嗎？
□ Mock 邊界用 connectionService.getClient() / similar 而不是 mock 整個底層 library
□ 確認 process.env mock 後 afterEach 清掉，避免 test 互相污染
□ Push 前明白告訴 Leo「我跑了哪些 test, 結果 X/Y pass」
```

## 同類

- [[start_dev_iron_rule]] — npm run start:dev / build 必須過（compile）
- 本條 — 加 unit test（behavior）
- 兩條合起來 = 「compile + behavior 都驗證才能 push」

## Bonus: 對 prod-impacting branch 流程改善

未來：
- 開 PR 設成 draft，讓 CI 跑完才 mark ready
- 或先 push 到 staging-only branch（不 trigger prod deploy）試
- 或 staging environment 先 deploy 觀察
