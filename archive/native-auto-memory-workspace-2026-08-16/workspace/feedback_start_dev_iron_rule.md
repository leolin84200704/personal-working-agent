---
name: start-dev-iron-rule
description: "npm run start:dev (and any build) must always pass on a branch I touch — never dismiss errors as \"pre-existing\" or \"stale environment\"; find the root cause"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e63993b2-cb7b-4413-b6bf-db5a669e4f69
---

**鐵律**:任何我動過的 branch,`npm run start:dev` / `npm run build` **100% 必須過**。出現 type / runtime / build error 時,**絕對不要當「pre-existing」或「stale environment 假象」放掉** —— Leo 強調過多次,過去也有過幾次「我以為是別人的問題,但最後是我自己創造的」。

**Apply**:
1. 看到 build / start:dev 失敗 → 假設**是我造成的**,找到為止。
2. 仔細追:branch 切換、untracked 檔(從別的 branch 帶過來的 schema migration 等)、generated 程式碼(prisma client、proto)、env / node_modules 狀態。
3. 若真的對應某個非我的 issue,也要修(讓 start:dev 過)而非略過。

**VP-16521 session 翻車案例**:LIS-transformer-v2 切 branch 後,`npm run build` 跑出 18 個 `specialties` 型別錯誤(`v2_calendar` 欄位)。我下了「stale generated prisma client 假象,build 後就 0 了」的草率結論。
- 真因:之前在 `feature/leo/VP-16499` branch 跑過 `prisma generate`(那邊 schema 有 specialties),client 寫進 `node_modules`;切到 VP-16521 branch(schema 沒 specialties)時,**沒重跑 generate** → client/schema drift。
- 真修:`npx prisma generate` + `npx prisma generate --schema=prisma2/schema2.prisma`(本 repo 雙 schema)。
- 易忽略:**本 repo `npm run build` 的 `prebuild` 只是 `rimraf dist`,不會跑 prisma generate**;`start:dev` 也不會。client 必須手動對齊。

**Why**:在我自己造成的問題上把錯當成環境假象,會把炸彈交給下一個人 / 下個 deploy。Leo 看 PR 之前希望 branch 是乾淨可起的。鐵律的目的是強制我「歸因到自己 + 找到底」。

相關:[[feedback_no_overgeneralize_from_single_case]] 是相反方向(別過度泛化);這條是「別把自己造成的問題當別人的」。
