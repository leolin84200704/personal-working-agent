---
name: project_emr_shortcut_sync
description: EMR shortcut auto-sync 討論 — VAREQUISTION(test/package) vs VACP(custom bundle) 定義 + 架構結論(該上游做不該 emr-v2)
metadata: 
  node_type: memory
  type: project
  originSessionId: 99dcff7b-017c-4aa9-b3ee-802733ba4be2
---

2026-06-17 Slack/huddle(Xiaoye Li / Terry Zhang / Ray / Leo)討論 **EMR shortcut auto-sync**。Ray:「後端(Leo)要加東西,Ray 再給 code」。大家(含 Ray)都不太懂機制,Leo 要我解釋並給架構意見。

**兩種 OBR.4 battery code(emr-v2 `obr-parser.service.ts` 按前綴分派):**
- `VAREQUISTION{id}` → **TEST / package**(標準項目,全域 catalog,所有診所通用)。key=`uniqueemrcode`(全局唯一);來源 pricing API `getLegacyPackagePriceMapping`。例:`VAREQUISTION463`=Gut Zoomer 5.0、`VAREQUISTION325`=Tick Borne 2.0。(拼字是 REQUIS**T**ION,少一個 I;Ray 寫的 VAREQUISITION 是口誤。)
- `VACP{id}` → **custom BUNDLE**(客製套餐,**customer/clinic 專屬**)。key=`oldOrderTypeId,customer_id`(clinic_id fallback);來源 bundle API `getLegacyBundleMapping`(promotion)。例:`VACP148201`=Revolution Health 的「Vibrant Panel 148201」,換別客戶可能查無/不同。
- 另有 `VATEST{id}`=單一 test、`discountpanel{id}`=折扣 panel、純數字=同 VACP 的 custom bundle。

**關鍵事實:** emr-v2 **只是下游消費者** —— catalog cache 每 30 分鐘 `@Cron` re-pull(`order-mapping-cache.service.ts:50`),custom bundle 有 `expireTime` 會到期。資料與控管權都在**上游 pricing/bundle(api.vibrant-wellness.com)**,custom bundle 由上游(pricing/ops)建。

**架構結論(Leo + 我 2026-06-17):**
1. shortcut sync **不是一次性**:catalog 動態(新項目/bundle 建立/到期),必須持續 sync。
2. **VACP 非 emr-v2 控管**:資料在上游。
→ 該由**上游 / 既有 portal catalog API** 負責,**不該在 emr-v2 蓋新 endpoint**(否則 emr-v2 變成「下游把上游資料再轉發一次」,多一跳 + 重複擁有權,freshness 還是看上游)。emr-v2 唯一獨有的是 **code 格式規則**(package.uniqueemrcode→VAREQUISTION;bundle.oldOrderTypeId+customer→VACP)。emr-v2 該做的只有繼續正確 parse 進來的 code(已會)。

**待釐清(huddle 三問,結果未定):** (1) VW portal/上游是否已有「per-customer orderable catalog」API(本來就在 portal 顯示給人下單 → 很可能有,接那支即可,emr-v2 不用動);(2) shortcut sync 的 owner 是上游 catalog 團隊還是 EMR 整合(資料在上游→偏前者);(3) 若最後仍要 emr-v2 出 endpoint,那只是包一層 workaround、非正解。相關 [[project_emr_backend_retired]]。
