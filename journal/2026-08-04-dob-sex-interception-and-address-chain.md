---
date: 2026-08-04
slug: dob-sex-interception-and-address-chain
related: [VP-17544, VP-17587, VP-17584, VP-17598, VP-17591, VP-17480]
distilled: false
---

# DOB/Sex 攔截上線，與一條追了四層服務的 address 鏈

兩張票，一天。共同主題是「每一層看起來都正常，但我沒驗證它真的在做我以為的事」——
這輪四個誤判都是同一個形狀，而三條 factory lesson 就是從中蒸餾出來的。

## VP-17544：攔截 + 告警

### 探索出來的東西比 ticket 寫的更嚴重

ticket 只要求「攔截缺 DOB/Sex 的 EMR 訂單」。實際讀 code 發現兩個既有缺陷：

1. **Sex 缺失會被靜默偽造成 Male**。`patient-detail-parser.service.ts:128` 把任何非
   f/female 的值（含空值）normalize 成 `'Male'`，所以下游那個 `isBlank(patient_gender)`
   檢查在 HL7 路徑是**死碼**。這不是 silent failure，是 silent wrong answer。
   → 攔截必須讀 normalize **之前**的 raw PID-8。
2. **DOB 缺失被貼成 `emr_code_not_found`** → 按 LTM triage 表那是丟給 Order team 建 bundle
   的分類，owner 全錯；然後 retry 耗盡靜默死掉。

### 排除掉的路

- **ACK 回拒（PRD Open Q2 的其中一支）不可行**：進單是 SFTP 拉檔（無 inbound 連線）、
  無 MLLP listener（`HL7_MLLP` 只是兩個 enum 值零實作）、`generateAcknowledgment` 是零呼叫者
  的 stub、而且就算能回，檔案最多 15 分鐘後才被抓到 —— 一小時後的 ACK 不是 ACK。
  PRD §7 自己也把 provider-facing 回饋排在 Phase 2，與 4.3-12 自相矛盾。
- **accept-and-hold** 會退化成 reject 的慢速吵版本：檢查讀的是進來的檔案不是 DB 病人，
  vendor 重送是全新檔案新 MSH-10，hold 沒有任何東西能讓資料出現。
- **把檢查推到上游 eligibility**：HL7 路徑根本不呼叫 eligibility check（只有 API 路徑有），
  要接進去遠大於這張故事。

### Leo 的原話與它改變了什麼

> 「看起來是現在沒有，我不理解為什麼做不到。在 parse 的時候直接辨別出來沒有填 DOB/SEX
> 然後發錯誤 slack 不行嗎？」

我把「emr-v2 沒有 Slack client」寫成 finding，讀起來像障礙。**「要新增」跟「做不到」是兩件事。**
而且這句話暴露我把 PRD 12（ingestion 失敗行為）跟 13（internal alerting）混成一件 ——
PRD 本來分開，AC 的「no silent failure」用內部告警就滿足，ACK 只是加分項。
**混合兩條需求會憑空製造出一個不存在的 blocker。**

> 「O/U/Other 這種也要 alert 並且擋住，我們只接受 F/M/Female/female/male/Male」

照 case-insensitive 白名單做（VP-17471 修的就是大小寫），並把同樣的「可辨別」標準用到 DOB
（8 碼須為真實且非未來的日期 —— 現況 `19850732` 這種爛值會原樣通過、`calculateAgeFromDob` 回 0）。

> 「但我以前確實有 sentry message 傳到 ...C08C59A6TMF」

**這句推翻了整個實作方向。** 我寫完一整個 Slack notifier 才發現告警機制本來就有 ——
Java 的 `ParseOrder.java:359` 在 `retryNum == 1` 時 `Sentry.captureException`，
經 project 49 → alert rule → Slack。emr-v2 遷移時把**整個 Sentry 上報**掉了
（package.json 零 `@sentry/*`，只剩 ConfigMap 佔位符）。
而我的觸發點（`next === 0`）跟 Java 的 `retryNum == 1` **是同一時刻** —— 從第一原則推導撞對。

我找漏的根因有兩層：**(a) 關鍵字**——我搜 slack/webhook/alert/pagerduty，那組 RPC 叫
`FeatureAccess`、那個機制叫 Sentry；**(b) 搜錯 source**——第一輪只搜 `lis-backend-emr-v2/src/proto`，
那是 **subset 副本**（實測 `Object.keys(service)` 確認零個 Feature* RPC）。
→ **consumer repo 的 proto 副本不能用來回答「這個 service 有什麼 RPC」。**

> 「用 project 49，先讓告警上線」

我先前問他選 project 時列了「新開」選項，他選了，結果「要建 project + 設 rule」卡了一天。
他回頭問「為什麼不能沿用」時我才發現整條路早就驗證可用。
**能立刻通的既有通道勝過需要別人動手的乾淨通道**，尤其當缺點會隨舊系統退役自然消失。
（Sentry 按 exception type 分組，`EmrOrderException` vs `EmrOrderAbandonedError` 天生分開，
所以共用 project 不會混淆。）

## VP-17591：address 追了四層，元兇不在我們家

Leo 要我跟 VP-17544 一併看 —— 對的，上游 eligibility 的完整性檢查是 **DOB + gender + address**
三項，VP-17544 做了前兩項，address 這項在 emr-v2 是壞的。

### 我最貴的錯誤

我驗證了「emr-v2 內部拿不到 address」（正確），**卻沒驗證那個值有沒有離開 emr-v2**。
`PlaceOrderRequest` 的 DTO **完全沒有 address 欄位** —— 只要一開始打開它看一眼就會發現。
我等到修完、測完、PR merge、prod deploy、live 驗證通過**之後**才發現。

**沿路每個訊號都是綠的**，因為那些訊號測的是「我改的東西有沒有正確運作」，
不是「我改的東西是不是問題所在」。

### 逐層排除（每一層的邏輯都對）

| 層 | 結論 |
|---|---|
| emr-v2 place-order | DTO 無 address 欄位 → 不送 |
| order-management `message.go:618` | 用 `IsPrimaryAddress` 但有 `[0]` fallback；且是 Kafka addon |
| billing concierge `:553` | 用 `shipping`，退到 provider office address |
| **billing `buildCompletePatientInfoMap:4433`** | 邏輯正確（`shipping`、不看 primary）→ **輸入為空** |
| coreSamples `get-patient-by-id` → `readPatient` | **有** `include: { patient_address: true }` |
| 時序 | `address_id` 與 `patient_id` 連號，`patient_create_time` 2025-12-09，訂單 2026-07-31 → 早 8 個月 |

決定性線索：payload 的 `country:"238"` 正是 billing 那個 method 的**預設值** → 迴圈沒進去
→ billing 手上的 `patient.getPatient_address()` 是空的。每層邏輯都對、資料也在，
結果卻空 ⇒ 執行期問題（反序列化 NPE / 部署版本 / CoreService 指向），不是邏輯問題。
billing 的 pod 不在我的 kubeconfig → 交診斷，不自己開票（別人的 service）。

### 順帶推翻自己一個斷言

我一度說 `is_primary_address` 是這張票的原因。它在 emr-v2 內成立
（71% 的病人沒有 primary 標記，而舊 code 拿它當唯一條件），
但**billing 和 order-management 從來不看那個欄位** —— 跨服務外推沒驗證。
另外查到那個欄位對病人地址**已實質廢棄**：833,404 筆 `shipping/primary=0` vs 251,608 筆
`primary=1`，最近建立的全是 0。

### Leo 定的業務規則（比我的 fallback 更嚴）

> 「有 Gut Zoomer（或任何需要判別 NY 的測試）一律只能以 HL7 為標準，沒有就連 db 都不看
> 直接拒單。多收錢的問題一定要 customer 提供完整訊息，否則因搬家等原因會有財務問題，
> 不能到我們這裡。」

我原本做「HL7 優先、沒有才用 DB」—— 那對寄 kit 對，對 NY 判定**錯**：舊地址（病人搬家）
會讓 $80 收錯或漏收，風險落在我們身上。所以拆成兩個欄位：
`patient_state`（檔案→DB，寄件用）與 `inbound_patient_state`（**只有檔案**，NY 判定用），
後者無條件設定（含 undefined）讓「這張訂單沒告訴我們」表達得出來 → `decideGzNy` 走既有
`NY_ADDRESS_REQUIRED` 拒單。範圍只改 HL7 路徑；`assembleWithNyRouting`（API 進單）不動,
因為那條路呼叫方不傳 address，且有 eligibility check 守著。

## 三個工具/流程層面的教訓（已進 factory #17/#18/#19）

- **`void somePromise()` 丟棄的是回傳值，不是 rejection** —— unhandled rejection 讓 Node
  結束 process，於是一個「失敗也不該影響主流程」的告警旁支反而會殺掉服務。
  是我自己寫的測試（`mockRejectedValue` 讓 jest worker crash）抓到的。
- **搜尋 flag 用錯不會報錯，只會靜默降級成另一個搜尋** —— `rg -r` 是 `--replace`，
  `-rn`/`-ril` 把後續字母吃成 replacement 並停用 `-i`/`-l`/`-n`。一天踩三次：
  一次讓我把自己的 bug 誤診成終端顯示層問題（前一次的正解不是這一次的先驗）、
  一次配 `2>/dev/null` 製造假的「0 hits」、一次漏掉 `Slack.java`。
- **repo 裡的部署設定不是 runtime 真相，兩個方向都會騙你** —— 同一天違反三次：
  `MY_POD_NAME` 不在任何 manifest 但 prod 5370/5372 筆有值（我據此差點開錯票、
  還為了消 guard 警告移除欄位寫入）；`SENTRY_DSN` 佔位符在但 SDK 從未安裝；
  `deployment.yaml` 宣告 `secretRef` 但那個 secret 根本不存在（我還照著叫別人去填）。

## 一個尚未定案的第四條候選

**修「資料沒傳到下游」的 bug 之前，先確認那筆資料真的由你這端傳送** —— 打開送出去的
DTO/payload 型別確認欄位存在，再追它為什麼是空的。與上面三條同一家族：
`void` 看起來忽略了回傳值、搜尋看起來執行了、config 看起來是設定來源、
修改看起來會生效 —— 四個都是「某環節看起來正常，但我沒驗證它真的在做我以為的事」。

## 驗證方法上學到的

- **rolling deploy 的完成判準要綁「新 pod 的身份 + 就緒」**，不能用
  `deployment.status.readyReplicas`（它在 rolling update 期間計入舊 pod）。我第一版
  Monitor 就是這個假訊號 —— 而那正是 factory lesson 第 12 條寫的，我寫完還踩。
- **驗證判準的錯誤方向系統性偏向「通過」**。live-verify 的 SQL 我把 UTC 22:30 誤寫成 15:30，
  撈到一整天的舊成功 row；只因為另一個 bug（`finished=true` vs Prisma raw 的 `finished=1`）
  才沒誤報。那是運氣不是設計。改用 **`id > baseline`**（單調遞增、無時區語意）。
  最便宜的自檢：**「如果現在什麼都沒發生，這個判準會不會通過？」**
- **on-prem pod 是否已更新，只能靠 DB 的 `last_update_pod_name`** —— 那個 cluster 不在
  本機 kubeconfig。兩次 deploy 都靠新 hash 出現在真實訂單上證明（`546b6869b8`、`777c956c9b`）。
- **共用 repo 上有並行 agent/job**：我的 commit 一度落到背景 job checkout 的
  `bugfix/leo/triage-prompt-step3-prefix-lookup` 上，而 `git push origin main` 推的是不含它的
  舊 main（卻印出 "STM pushed"，因為 `| tail` 吃掉了 exit code）。commit 前要確認當前 branch。

## Leo 的兩個判斷勝過我的

1. **90 筆歷史略過**。我說「event-time 告警無法發現已卡住的 backlog，所以需要週期性 sweep」——
   但 VP-17533 已把所有 throw 收攏進 `markFailure`，**未來每筆耗盡都會即時告警、不會再累積**，
   清歷史只是考古。**提出「需要新機制」前，先確認既有機制是否已覆蓋未來的案例。**
2. **沿用 Sentry project 49**（見上）。
