---
id: business-model
type: ltm
category: technical
status: active
score: 0.401
base_weight: 0.9
created: 2026-06-07
updated: 2026-06-07
links:
- INCIDENT-20260518
- LBS-1487
- QH-1130
- QH-1591
- QH-918
- QH-919
- VP-15460
- VP-16154
- VP-16169
- VP-16232
- VP-16391
- VP-16410
- VP-16499
- VP-16513
- VP-16520
- VP-16521
- VP-16629
- VP-16664
- VP-16785
- VP-16787
- VP-16859
- VP-16921
- business-model-deep
- emr-integration
- failures
- repo-catalog
- repos
- ticket-routing
tags:
- business
- product
- revenue
- monetization
- domain
- vibrant
summary: 'Vibrant America / Vibrant Wellness business model reconstructed from code:
  products (60+ lab tests), B2B2C customer model, EHR platform, phlebotomy network,
  and the charging→billing→payout revenue/money-flow. Context for interpreting PM
  tickets.'
---



























# Vibrant America / Vibrant Wellness — 商業模式 (從程式碼反推)

> 目的：理解公司「賣什麼、賣給誰、怎麼賺錢」，以便解讀 PM ticket 的業務語意（哪個 fee、哪種 payer、哪條金流）。
> 來源：2026-06-07 對 repo 的證據掃描（report-pdf / LIS-Report / pricing / charging / billing / payout / accounting / 各 portal / emr-v2）。
> 標記：**[證據]** = code 直接佐證；**[推論]** = 由證據合理推斷，未 100% 確認。
> **計算層細節（markup/稅/coupon 公式、payout 分潤公式、payout 資格 state machine、PNS 命名歧異）見 `business-model-deep.md`。**

---

## 0. 一句話定位

Vibrant 是一家**功能醫學 / 健康 (functional & wellness) 臨床檢驗實驗室**，核心賣 60+ 種專科檢驗 panel（各種 "Zoomer"）。商業模式是 **B2B2C**：主要把檢驗賣給**功能醫學診所 / 醫師 (practitioner)**，醫師為其病患下單；同時提供一整套**診所平台**（自有 EHR、排程、即時通訊、AI 病歷、行動抽血網路、病患 portal），並靠 **markup + 收款 + 撥款分潤** 的金流賺取多層收入。**[證據+推論]**
**注意：未見保險請款 (insurance billing) 邏輯，payer 是 patient-pay / clinic-pay 的 cash-pay 模式** — 典型功能醫學自費市場。**[證據：billing_type 只有 customerPay/patientPayNow/patientPayLater，無 insurance]**

---

## 1. 品牌與網域 (Brands & Domains)

| 品牌 | 定位 | 網域 | 用途 |
|------|------|------|------|
| **Vibrant Wellness (VW)** | 現代/整合的 wellness、功能醫學產品線（主力） | `vibrant-wellness.com`, `api.vibrant-wellness.com`, `portal.vibrant-wellness.com`, `report.vibrant-wellness.com` | 診所 portal、病患報告、主要 order/charging API |
| **Vibrant America (VA)** | 較舊/廣義 lab testing；trans-service API | `vibrant-america.com`, `api.vibrant-america.com` | trans-service（vitals/medication/file）、BEST_DEAL 定價 |
| **Phlebotomy Network** | 抽血排程/物流 | `phleb.vibrant-wellness.com` | blood-draw-maps 抽血點預約 |

- pricing 的 `item.go` 用 **`VA` / `VW`** 兩個 division 區分產品線。**[證據]**
- 報告類型前綴：`VA*`=Vibrant America(legacy)；多數 Zoomer 屬 VW。**[證據]**

---

## 2. 產品線 — 賣什麼 (Product Catalog)

主檔：`report-pdf/src/service/ReportService/ReportMappingInfo.js`（65+ report type registry）+ `LIS-backend-v2-pricing/ent/schema/`（item/merchandise/promotion）。**[證據]**

### 2.1 核心：專科檢驗 panel（"Zoomer" 系列，60+ 種）
按類別（每類常有 DBS = Dried Blood Spot 乾血片版本 + 多版號 v1/v2/v4/v5）：

- **食物 / 過敏抗體 (Zoomer 抗體系列)**：Wheat(WZ)、Corn(CZ)、Egg(EZ)、Soy(SZ)、Peanut(PZ)、Seafood(SFZ)、Dairy(DZ)、Grain(GZ)、Lectin(LZ)、Mammalian(MZ)、Nut(NZ) — 各含 DBS 版
- **食物敏感 (Food Sensitivity)**：FS、Food One Click(FOC)、Profile 1/2(FSP1/FSP2, IgAIgG 與 C3dIgG4 變體)、Complete Food Profile(CFP)、Food Additives(FA)
- **腸道 / 微生物 (Gut)**：Gut Zoomer(GUT/GUT4/GUT5)、Candida+IBS Profile(CIP)、UTI Zoomer(UTI)
- **神經 (Neural)**：Neural Zoomer(NEUZ)、Neural Zoomer Plus(NEUZP)
- **荷爾蒙 (Hormone)**：Urinary Hormones(UH)、Salivary Hormones(SH/SH2)、Hormone Zoomer(HZ)、Cortisol Awakening Response(CAR)
- **毒素 / 環境 (Toxins)**：Toxin Zoomer(TTS)、PFAS、Heavy Metals(HM/HM2/HM2B)、Environmental Toxins(ET)、Mycotoxins(MY)、Toxin Genetics 唾液/血(TGS/TGB)
- **營養素 (Nutrients)**：Micronutrients(MN)、Nutrient Baseline/Intracellular/Zoomer/Genetics(NTB/NTI/NTZ/NTG)、Whole Blood Nutrient(WBN)
- **蜱傳疾病 (Tickborne)**：TB1/TB2(+DBS)、Tickborne Antibodies(TA)、Lyme Autoimmune(LA)
- **心血管 (Cardio)**：Cardio Zoomer(CDZ)、CardiaX(CD2/CDS2)、Cardio Genetics(CDG)
- **細胞 / 氧化壓力**：Cellular Zoomer(CZS)、Oxidative Damage/Genetics/Profile(OSU/OSG/OSP)
- **遺傳 / 甲基化**：Methylation(ME/MEG)
- **其他專科**：Organic Acids(OAC)、Neurotransmitters(NT)、Virus Infection(VI)、Autoimmune Zoomer(AZ)、Foundation Zoomer(FDZ)、NutriPro(NP)

### 2.2 周邊商品 (Merchandise)
`pricing/ent/schema/merchandise.go`：type = `item`(實體商品，如補充品 supplements / kit) 或 `service`(服務)。有 status(draft/active/inactive)、return_and_refund_info、clinic 範圍(-1=global)。**[證據]** → 除檢驗外也賣補充品 / 服務。

### 2.3 套組 (Bundles / Shortcuts / Packages)
`Shortcut` entity = 預設檢驗套組，可 `is_practice` / `is_at_home`(在家採檢)、綁 customer/clinic、payload JSON 組成、版控+restore。`ShortcutBundle` 綁 Promotion 做套組定價。**[證據]** → 醫師可建客製 panel 套組。

---

## 3. 客戶與通路 (Customers & Channels) — B2B2C

### 3.1 客群 (角色 enum 證據)
- **醫師 / 診所 (B2B，主客戶)**：role `provider`(個別醫師)、`clinicadmin`/`clinic_admin`/`clinic`(診所管理)、`navigator`(病患協調員/CAM 從業者)、`customer`(practice 客戶代號)。
- **病患 (D2C，次要)**：經 PNS portal，guest 登入(accession id+生日+姓名 驗證) 或帳號登入(+2FA)。mutation `patientGuestLogin` / `patientAccountLogin`。**[證據]**
- **內部**：`agent`(支援/履約)、`admin`(系統管理)。

### 3.2 下單通路
1. **醫師代病患下單**（主流）：在 EHR portal 的 order center(`ehr-frontend/src/views/va-orderTest/`) 選病患→選 panel→付款方式→確認。**[證據]**
2. **病患自助下單 (D2C)**：PNS portal。
3. **嵌入第三方 EHR**：醫師在自己的 EMR 系統開單，經 HL7/SFTP 進 Vibrant。**[證據]**

### 3.3 多租戶隔離
`clinic_id`(主隔離) / `customer_id`(practice) / `patient_id`。clinic **150105** 是特殊的 **Clinical Consult / 遠距門診診所**（calendar 有 hardcode 多個 calendar id、telehealth 排程），ticket 常見此 id。**[證據]**

---

## 4. 平台與加值服務 (Platform & Value-Add)

賣的不只檢驗，而是一整套診所營運平台：

- **自有 EHR (ehr-frontend)**：Workbench(臨床工作區)、Pegboard(病患卡片牆，含 order/medication/billing/notes/appointment/questionnaire/form/contact 卡)、行事曆排程、即時訊息(Rocket.Chat `api.vibrant-wellness.com/v1/ehr/chat`)。**[證據]**
- **AI 病歷 (encounterNotes)**：醫病對話錄音→Azure Whisper 轉錄→GPT/Claude 產 SOAP 摘要→pgvector 語意搜尋；PHI 用 AES-256+RSA-2048 加密、HIPAA audit。**[證據]**
- **行動抽血網路 (Phlebotomy / "PNS")**：PNS = **Patient Navigation & Sample tracking**（pns-portal README）。行動到府抽血 + 在診所抽血選項；`phleb.vibrant-wellness.com/blood-draw-maps` 找抽血點預約；`need_blood_draw` / `concierge_blood_draw_options` / `bloodKitDeliveryMethod`。**[證據]**
- **遠距門診 / Clinical Consult**：calendar + Zoom 整合、預約、provider/patient/location 參與者；clinic 150105 專用。**[證據]**
- **病患 portal**：
  - **PNS-Singlepage**(履約流程)：付款→問卷→出貨/採檢→抽血排程→專科問卷(Cardio/Gut/Hormone Zoomer)→NY 州合規表。
  - **pns-portal**(訂單追蹤)：查訂單/帳單/報告/follow-up 出貨；i18n 英/西。**[證據]**
- **問卷 / 評估**：各 Zoomer 專屬問卷 store + NY 表單。**[證據]**
- **診所 admin portal (vibrant-wellness-portal)**：announcement/coupon/lab test 設定/臨床排程/webinar/science 內容/AI chat；clinician 管理(specialties/availability/OPD)。**[證據]**
- **practice 分析 dashboard**：營收、訂單分析、provider 績效、AI Insights(practice vs provider view)。**[證據]**

### 第三方 EHR 整合（整合「進」客戶既有系統）
| Vendor | code | 傳輸 | 備註 |
|--------|------|------|------|
| ChARM EHR | CHARM | SFTP + HTTP | 雙向 HL7 ORM^O01(orders) / ORU^R01(results) |
| OptimalDX | OptimalDX | SFTP | 結果遞送(legacy Syncplify) |
| THM (The Gundry Lab) | THM | SFTP | 用原始 Order ID(非 Vibrant barcode) + PDF |
| Elation Health | — | HL7/SFTP | `labs.elationemr.com` |
| 通用框架 | `ehr_vendors` 表 + vendor-management module | SFTP/HTTP/HL7 | 自助新整合 onboarding，狀態 PENDING_REVIEW→IN_PROGRESS→LIVE |

詳見 `emr-integration.md`。**[證據]**

---

## 5. 盈利模式 / 金流 (Revenue & Money Flow) — 核心

服務鏈：**charging(收款) → billing(發票/結算) → payout(撥款分潤)**，旁邊 accounting(折扣/concierge fee)、pricing(定價/promo)。各服務容器內 HTTP 多 `8084`，靠 Kafka 串事件。**[證據]**

### 5.1 誰付錢 (Payer)
billing_type：`customerPay`(客戶付全額)、`patientPayNow`(結帳即付)、`patientPayLater`(服務後付)；account type：`customer` / `clinic` / `patient`。**無 insurance** → cash-pay。**[證據]**

### 5.2 付款方式與分期
- 卡(card, Stripe/Stax)、ACH、內部 credit、數位錢包(Apple Pay/Google Pay/Stripe Link)、**HFSA/FSA 健康帳戶卡**。**[證據]**
- token platform：`stripe` / `stax` / `stripe_zb`(Zebra Biology 帳) / `splitit` / `internal`。**[證據]**
- **BNPL 先買後付**：Afterpay/Clearpay、Klarna、Splitit(分期)。**[證據]**

### 5.3 收費項目 (Fees) — 病患/診所付
- `va_processing_fee` / `lab_processing_fee`(實驗室處理費)、`concierge_fee`(到府抽血/協調服務費)、`consultation_fee`(諮詢費)、`international_shipping_fee`(`import_fee`/`export_fee`)、blood draw fee、redraw fee。**[證據]**
- charge_type：testorder / item / giftcard(禮物卡) / batch / bill / subscription / bulkorder / kitorder。**[證據]**

### 5.4 醫師經濟學 (Provider Economics) — 公司賺多層、醫師也賺
- **Markup scheme**：醫師可對檢驗加價（No markup / 百分比 / 固定額），差額是醫師利潤。`pricing/handler/markup.go`。**[證據]** → 公司賺 base，醫師賺 markup。
- **撥款分潤 (payout)**：payout type `profitout`(檢驗利潤分潤)、`merchandiseout`(商品分潤)、`conciergeout`(concierge 分潤，與抽血師拆)、`cashout`(餘額提領)。waitlist 追 profit/merchandise/concierge amount+paid。經 **Stripe Connect** 撥到醫師/診所/抽血師銀行帳戶。**[證據]**
- **獎勵計畫 (reward)**：clinic 推薦/忠誠 reward scheme，計入 payout。**[證據]**
- 收款人 account：`customer`(個別醫師)、`clinic`、`phlebotomist`(收 concierge/抽血費)。**[證據]**

### 5.5 經常性收入 (Recurring)
訂閱：`charge_type=subscription`，frequency/interval/start/end/amount；用於**定期檢驗**與**定期 kit 出貨**自動扣款。`charging/handler/subscription.go`。**[證據]**

### 5.6 促銷 (Promotions)
coupon code(verify/redeemable/usage 限制 global+account)、promotion(percentage_off / absolute_off / final_price，可限品項/帳號類型/時間窗)、highlight card(主打)、best-deal(Zoomer 套組最優價)。**[證據]**

### 5.7 多幣別 / 國際
USD(預設)/GBP/EUR/CAD(pricing) + billing 另見 CHF/NOK/DKK/SEK/MXN/JPY；有 exchange_rate 管理 + 國際進出口運費。**[證據]** → 賣到英、歐、加、北歐、墨、日等。

### 5.8 金流全景
```
病患/診所結帳 → CHARGING(Stripe/Stax/BNPL/HFSA 收款, webhook 對帳)
  → BILLING(開 charge/invoice、Apply 沖帳、credit/discount、餘額)
  → PAYOUT(算 profit/merchandise/concierge 分潤 → Stripe Connect 撥款給醫師/診所/抽血師)
  ↔ PRICING(定價/markup/promo/tax)  ↔ ACCOUNTING(折扣/concierge fee, sunset 中)
```

---

## 6. 收入來源彙總 (Revenue Streams)

**病患端**：檢驗費、lab processing fee、concierge/抽血費、國際運費、諮詢費、(加急費)、商品(補充品)、禮物卡。
**醫師端（公司抽成後分潤）**：檢驗 markup、profit share、商品分潤、concierge 分潤、推薦獎勵。
**經常性**：訂閱檢驗、定期 kit。
**平台價值**：自有 EHR + AI 病歷 + 排程 + 抽血網路綁住診所（提高黏著與下單量）。

---

## 7. 對解 ticket 的意義 (How this maps to tickets)

- ticket 講 **fee / charge / refund / payment method / BNPL / HFSA** → charging（收款）；**invoice / statement / settlement / apply / credit** → billing；**payout / profit / commission / concierge 分潤 / Stripe Connect** → payout；**markup / coupon / promotion / bundle / price** → pricing；**discount / concierge fee（舊）** → accounting-wsgi(legacy)。
- ticket 講 **某 report/Zoomer 不對** → LIS-Report + report-pdf；**reference range / test 設定** → LIS-Lab-test。
- ticket 講 **blood draw / 抽血排程 / phlebotomy / PNS** → PNS-Singlepage / pns-portal / LIS-Shipping / phleb 服務。
- ticket 講 **EHR 介面 / workbench / pegboard / chat / 病歷** → ehr-frontend / encounterNotes。
- ticket 講 **EMR 整合 / vendor / HL7 / SFTP** → lis-backend-emr-v2（見 emr-integration.md）。
- ticket 提 **clinic 150105** → Clinical Consult 遠距門診（LIS-transformer-v2 calendar）。
- payer 語意：PM 講「patient pay / customer pay」對應 billing_type；**沒有保險**，別假設 insurance flow。

---

## 8. 待確認 / 不確定 (Caveats)
- "PNS" 取自 pns-portal README "Patient Navigation & Sample tracking"；他處可能另有解讀(phlebotomy)，未跨檔完全一致確認。**[推論]**
- 各 fee 的實際拆帳比例（公司 vs 醫師 vs 抽血師）程式碼未明示金額，只見欄位結構。**[推論]**
- 保險請款「未見」不等於「絕對沒有」，但主 flow 是 cash-pay。**[證據範圍內]**
- 產品清單以 report type registry 為準，實際對外販售品項以 pricing item 表為準（兩者大致對應但非 1:1）。
