---
id: business-model-deep
type: ltm
category: technical
status: active
score: 0.2116
base_weight: 0.9
created: 2026-06-07
updated: 2026-06-07
links:
- VP-15460
- VP-16410
- VP-16520
- VP-16859
- VP-16921
- business-model
- failures
- repo-catalog
- repos
tags:
- business
- pricing
- payout
- revenue-split
- formulas
- pns
summary: 'Deep computational reference: exact pricing/markup/tax/coupon math, payout
  & revenue-split formulas (profit/concierge/merchandise/reward), payout eligibility
  state machine, and PNS naming. All code-backed with file:line. Reference when a
  ticket touches money math.'
---









# 商業模式深掘 — 計算層公式參考

> `business-model.md` 的計算層補充。這裡放**實際公式 + file:line**，供解 fee/markup/payout/coupon 類 ticket 時查。
> 標 **[DB]** = 值存資料庫非 code；**[code]** = 硬編在程式；**[推論]** = 推斷。
> 來源：2026-06-07 深掃 pricing / charging / billing / payout / order-management / accounting。

---

## A. 定價 / Markup / 稅 / Coupon 計算

### A1. Markup（醫師加價）— pricing 存定義，order/charging 套用
- 檔：`LIS-backend-v2-pricing/ent/schema/markup_scheme.go:18-29`
- `markup_type` 四種 **[code 列舉, 值在 DB]**：
  - `no_markup` — 不加價
  - `fixed_profit` — 加固定金額（base + value）
  - `added_percentage` — 加百分比（base × (1+value)）
  - `fixed_price` — 直接設定終價為 value
- `creator_type` 優先序：**`admin_force`(不可改) > `admin_suggest`(可改) > `provider`(醫師自設)**。`handler/markup.go:40-115`。
- ⚠️ **pricing service 只「存」markup 定義、不「套用」**；實際把 markup 算進訂單總額的程式在 order/charging 層。`item_type` = bundleId / packagePriceId / shortcutId。
- **醫師利潤來源就是這個 markup**（見 B1）。

### A2. 實際價格存哪 — 幾乎全 DB **[DB]**
- 權威價表：`item_price`（每 item 每幣別一筆 price）、`promotion_price`（每 promotion 每幣別 discount_value）、`fedex_delivery_fee`（export 運費 zone 查表）。
- **無 seed/fixture 真實價格**；prices 一律 DB 撈。
- **唯一硬編價例外**：`service/promotion.go:371-410` — item **181** 在 new_vw 選單強制 `70.0`、否則 `60.0`（覆蓋 DB 價）。**[code]**
- → 要「某 Zoomer 實際售價」必須查 DB `item_price` 表（需 Leo 授權連 prod）。

### A3. 多幣別匯率 — 硬編、非即時 feed **[code]**
- 檔：`global/constant.go:98-108` `ExchangeRateMapping`：
  `usd 1.0 / gbp 0.80 / eur 0.92 / chf 0.87 / nok 10.83 / dkk 6.90 / sek 9.90 / mxn 18.90 / jpy 169.78`
- 換算：`CeilToNearestTen(rate × usdValue)`（`handler/item_price.go:945`）— **無條件進位到最近的 10（分）**。
- ⚠️ 匯率寫死在 code，調匯率＝改 code 重佈署。

### A4. 稅 — 全交給 Stripe Tax **[外部 API]**
- 檔：`handler/tax.go:26-50` + `service/stripe_service.go:70-104`。
- 一律以 USD 送 Stripe，帶 customer address(country/state/zip/city/line1) + line item `TaxCode` + `TaxBehavior` + shipping cost；回 `TaxAmountExclusive`(cents)÷100。
- 課稅與否由 Stripe 依地址 + TaxCode 決定（醫療檢驗多有免稅碼）。

### A5. Coupon / Promotion 數學 **[code 邏輯 + DB 值]**
- 檔：`service/promotion.go:205-550`。三種 discount type：
  - `percentage_off`：`deduction = value × item.price`，逐 item 套；**與 bundle 比，取省最多者**（greedy）。
  - `absolute_off`：固定額度從高省 item 往下扣，扣完為止。
  - `final_price`：直接設套組終價。
- 資格 gate：日期窗、allowlist(customer/clinic/patient)、`redemption_limit_global` / `redemption_limit_account`（數非 voided 的 `coupon_usage`）。
- **特殊 coupon [code]**：
  - `bVibrant`：absolute_off `400 × rate`，**累積上限 `600 × rate`**，超過報錯。
  - concierge 減免券 `1BDCSF/B2DCSF/BD3CSF/BDC4SF/BDCS5F`：type=`waive_concierge_fee`，免 **$99** concierge fee。
- **不可疊加**（一單一券，無合併折扣 code）。
- 用量：`RecordCouponUsage`(下單)、`VoidCouponUsage`(取消單)。

### A6. 各項 Fee 計算 **[混合]**
- **Shipping fee**（`service/shipping.go`）：
  - 美國 & 屬地(country 233/238/239)：**免運**。
  - 加拿大/印度：**硬編 USD**（如加拿大 blood import 42.17 / nonBlood 26.53 / blood export 31.61 / nonBlood export 19.89；印度更高）再乘匯率。
  - 其他國：import = 依幣別 flat fee（**elevated tests 849/853/842** 收較高的 elevated flat fee）；export = 查 `fedex_delivery_fee` 表（USD→乘匯率）。
- **Concierge fee**：預設 **$99**，可用券免除。
- **Lab processing fee**：**不在 pricing service**；由 setting 層 per customer/clinic 查（見 C1），非 flat，預設 0。
- 訂單總額組裝在 charging（`model/accounting.go:135-154`）：`Total = Subtotal − Discount + Tax + Fees`，多為**外部預算好再傳 PayRequest.Amount**。

---

## B. Payout / 分潤公式（公司 vs 醫師 vs 抽血師）

> 核心檔：`LIS-backend-v2-payout/service/eligibility.go`、`handler/manager.go`、`handler/transaction.go`。資料落 `waitlist` 表。

### B1. profit_amount（醫師檢驗利潤）**[code]**
```
profit_amount = earnings_from_markup + consultation_fee
```
- `earnings_from_markup` 在 order-management 算好（`service/order_query_service.go:314-316`：test item 的 markup 累加；非 test item markup=0）。markup 值來自 A1 的 `markup_scheme`。
- `consultation_fee` 來自 order（無 merchandise 時併入 profit）。
- 存 `waitlist.profit_amount` + `profit_detail`(JSON 明細)。

### B2. concierge / merchandise 折算 **[code]**（eligibility.go:158-202）
- **有 merchandise**：`merchandise_amount = merchandise_total_price + consultation_fee`（consultation 併入 merchandise_detail）。
- **無 merchandise**：consultation_fee 併入 profit_amount，concierge 不另開欄。
- **concierge_source**（billing `charge_billing_detail.go:676-684`）：`customer`→診所付（從 originalTotal 扣）；`patient`→病患付（從 modifiedTotal 扣）。

### B3. merchandise 淨額 — 按比例扣 Stripe 手續費 **[code]**（manager.go:164-177）
```
transaction_fee = merchandise_amount × (charge_fee_sum / total_order_amount)
merchandise_net = merchandise_amount − transaction_fee
```
- `charge_fee_sum` = 該 sample 全部 Stripe 手續費加總（`charge_fee` 表，`GetChargeFeeSumWithSampleId`）。
- profit 同樣按比例扣手續費（manager.go:181），明細記 `"transaction fee": -值`。

### B4. reward_value — RewardScheme 配對 **[code/DB]**（eligibility.go:130-156）
```
reward_value = Σ(matched scheme 的 target_value)  // 每 scheme 命中一次
```
- 依 clinic 查 `reward` 表；訂單品項命中 scheme.targeted_items 即加該 scheme target_value。
- reward 結算**不扣手續費**，settle 後清 reward_id。

### B5. Payout 資格 state machine **[code]**（manager.go:388-439 / transaction.go:355-371）
**ALL 條件成立才撥**：
```
order_paid == true
AND blood_tnp == false
AND non_blood_tnp == false
AND blood_unreceived == false
AND non_blood_unreceived == false
AND profit_paid == nil  (未付過)
```
- 任一不滿足 → flag 重查（profit 延 12h、reward 延 10h enqueue）。
- TNP/unreceived 由 `Core.GetTnpTestsResult` + `Order.ConfirmUnreceived` 取得（TNP ≈ Test Not Performed **[推論]**）。
- order_paid 由 `Accounting.GetCurrentOrderPaid` 取。
- **無最低門檻、無 hold、無 cliff**；>$0 且條件滿足即即時轉帳；**不可重複付**。

### B6. 撥款兩條路 **[code]**（manager.go:106-284 / transaction.go:336-472）
依 `setting_PM`（utility_setting）：
- **`payout_account`** → **Stripe Connect transfer** 直撥銀行。credit status 3→4。
  - Stripe `TransferParams`: `Amount=net×100` cents、`Destination=recipient.ConnectAccountID`、metadata `payout_type=profitout`、`payout_type_id=accessionId`。
  - 收款人 token = `{customerId}_{clinicId}` 或 `{clinicId}`（依 `setting_APUBD`=allow_usage_of_billing_delta 決定 account_type=customer/clinic）。
- **wallet / billing delta** → 進 accounting 帳戶餘額(credit)。credit status 3→1，發 `credit_disbursed` Kafka。
- credit status 生命週期：`2`pending / `3`ready / `4`payout initiated / `1`disbursed。

### B7. 分潤比例配置在哪（**無硬編百分比**）**[DB config]**
| 來源 | 表（repo） | 控制 |
|------|-----------|------|
| markup scheme | `markup_scheme`(pricing) | 醫師檢驗利潤率 |
| consultation fee | `order_fee`(order-mgmt) | 諮詢費 |
| merchandise + 退款政策 | `merchandise_items`(order-mgmt) | 商品分潤 + redemption window |
| payout 目的地 | `utility_setting`(setting-consumer) | wallet vs payout_account、是否用 billing delta |
| Stripe 手續費 | `charge_fee`(payout) | 自動按比例扣 |

---

## C. 其他費用 / 計費機制

### C1. Lab processing fee **[DB setting]**
- 非 flat，per customer/clinic 設定（`LIS-transformer/.../setting.billingn.service.js:369-414`），有 `lab_processing_fee` 與 redraw 專用 `returning_lab_processing_fee`，預設 0。

### C2. Redraw（重抽/重採）**[code]**
- 由 TNP/檢體不足觸發；Java `Redraw` entity（`LIS-backend-billing/.../entity/Redraw.java`）記 originalTestId/tnpTestId/sourceOrderId/tnpOrderId/sampleId。
- 流程：order note `redrawtest` → POST NewOrderService `/redraw` → 查 redraw 資格 → blood test 設 `isRedrawn=true`。重抽產生新 tnpOrder，收 `returning_lab_processing_fee`。

### C3. Gift card **[code]**
- `charge_type=giftcard`（與 testorder/item 同級，transaction.go 驗證）。購買建 giftcard 交易；兌換時當 credit/payment 抵扣；charging 層**無專屬餘額表**（餘額靠 billing credit 系統）。

### C4. Subscription 週期 **[code]**
- schema：frequency `daily/weekly/monthly/yearly` + `interval`(間隔數)、amount、start/end(預設 +10 年)、next_run/last_run、status(1 active/0 deleted)、`record_id`=Stax scheduled invoice id。
- 排程：batch charge job **每天 UTC 00:00 與 12:00 兩次**（`handler/scheduler.go`），後端用 **Stax scheduled invoicing**。
- 失敗：`batchCharge.go:228-231` →「下個營業日重試」，最終失敗 `VoidPayment`。

### C5. charge_type 用途 **[code]**（chargeInfo.go:20 / subscription.go:21）
`testorder`(檢驗) / `item`(商品) / `giftcard` / `subscription` / `bulkorder`(practice 批量) / `kitorder`(採檢 kit 出貨，`va-portal` `/generateOrderId/kitorder`) / `batch` / `bill`(僅 subscription 用)。

---

## D. PNS 全稱 — 各 repo 不一致（記錄歧異）

grep 全 repo，**PNS 縮寫在不同團隊/repo 解讀不同**，沒有單一官方答案：

| 解讀 | 出處 | 權威度 |
|------|------|--------|
| **Patient Navigation & Sample tracking** | `pns-portal/README.md:1-3` | pns-portal 官方 README |
| **Patient Notification Service** | `PNS-Singlepage/README.md`、`va-portal/CLAUDE.md` | PNS-Singlepage 官方 README |
| Patient Notification System | `LIS-transformer-v2/src/trans/pns-login.resolver.ts` 註解 | code 註解 |
| Patient Navigation System Portal | `feature_dashboard/pnsportal-done.py` | dashboard 描述 |

**結論**：兩個主要讀法並存 —「Patient **Navigation** & Sample tracking」(pns-portal) vs「Patient **Notification** Service」(PNS-Singlepage/va-portal)。解 ticket 時**別假設單一全稱**，依該 repo 的 README 為準。
- 營運上 `/ps/` API path（`phleb.vibrant-wellness.com/ps/...`）關聯**抽血(phlebotomy) location 服務**，與 PNS 縮寫的字面不同但同屬病患/抽血流程。

### pns-portal vs PNS-Singlepage 差異
| | pns-portal | PNS-Singlepage |
|--|-----------|-----------------|
| 用途 | 履約後：訂單/帳單/報告**追蹤** | 履約中：付款/問卷/採檢/抽血排程**流程** |
| 路由 | hash `/#/` | history `/pns_single_page_flow?...`，含 media→view 加密參數 |
| 建構 | Vite 5 | Vue CLI/Webpack 5 |
| GraphQL | 單一(PNS trans) | 雙(EMR calendar + PNS trans) |
| 付款 | 只顯示 | 完整 Stripe/Stax/BNPL/錢包 |

---

## E. 待 Leo 授權才能補的（需連 prod DB）
1. 各 Zoomer 實際售價（`item_price` 表，按幣別）。
2. markup_scheme 實際數值（各診所加價率）。
3. reward scheme 實際 target_value。
4. concierge fee 是否仍為 $99（code 硬編於減免券，實際 ConciergeFee 記錄在 DB）。
