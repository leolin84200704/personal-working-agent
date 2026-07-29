# 2026-07-29 — Beta clients 全鏈路 E2E + cancel gateway 修復（VP-17531）

Related: BETA-E2E-20260729, VP-17517, VP-17531, VP-17499, VP-17500

## 事件軌跡

1. Leo 給 5 組 beta client credentials，要求 emr-api order 全部 end-to-end。24/26 過：4 client 核心流程、GetHealthy 深度組（reclaim 循環/不去重/各種 422）、以及**第一次真實雙租戶驗證**（同 placerId 各自獨立下單 + cancel tenancy guard）— VP-17499 part B 之後的隔離終於有兩個真 tenant 可證。
2. 發現 gateway 是 `/v1/orders/*` → `/api/v1/order-intake/*` 的通用子路徑轉發 — cancel 404。開 VP-17531，加 controller 雙路徑 alias（`['order-cancel','order-intake/cancel']`），PR #297 當日 merge。**意外紅利：完全不需要 api-product 配路由**。
3. QA client token exchange 持續 500 — OAuth（Rust）服務、別組的 scope → 只回報證據不開票（VP-17522 教訓的第一次正確執行）。
4. 重測第一輪又 404：deploy 根本沒發生（last-applied 停在前一天）。期間**第二次 phantom monitor 讀值**（0be8faf pod "Running true"，事後連 RS 都查無此物）。Jenkins 拖了 ~2h 才真的 apply。
5. 真部署後：先 exec 驗 dist（`ALIAS_PRESENT`）再測 → 外部 gateway 7/7 全過。Leo 提醒 prod 已經 promotion（#298）— 我漏看；prod 用「dist exec + 無 token 401 探測」零副作用確認路由已通。

## 值得記的

- **部署驗證的最終形態：exec 進 pod 驗編譯產物內容**（grep dist 裡的具體變更字串），不是 image tag、不是 pod ready、更不是單次 kubectl 讀值。今天兩次靠它擋掉假陽性。
- 對外 API 的 404/401 差異是零副作用的路由探測器：401 = 路由通、服務在驗 token；404 = 路由斷。prod 驗證不需要碰任何真訂單。
- Nest `@Controller(['a','b'])` 陣列路徑在 v11 是合法的 — 本以為它沒生效，實際是 deploy 沒發生。差點誤修一個不存在的 bug；「先確認 code 有沒有真的在跑，再 debug code」。
- Gateway 通用轉發的行為要用實驗確認（404 的 upstream path 洩漏了轉發規則），不要相信「應該要配路由」的假設。
- 漏看 promotion #298：報告「prod 還沒有」前應該先 `git log origin/main` 確認 — Leo 一句話就抓到。

## Leo 原話

「這是有卡的beta clients, 請你把所有的emr-api order 的部分都測試一遍(end-to-end)」「prod 應該也是有的，你要不要看一下？」
