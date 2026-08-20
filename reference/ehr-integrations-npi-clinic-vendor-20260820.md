# ehr_integrations — NPI × clinic_id × EMR vendor inventory

> Snapshot: prod `lisportalprod2 / lis_emr.ehr_integrations` LEFT JOIN `ehr_vendors`,
> taken 2026-08-20 (UTC). Read-only.
> 目的：支援「所有 HL7 inbound order 改用 `customer_npi` + practice_id(clinic_id) 比對」的決策
> （Leo 2026-08-20 決定，取代今天的 ORC-12.1 → customer_id 比對）。

## 檔案

| 檔案 | 內容 |
|---|---|
| `ehr-integrations-npi-clinic-vendor-20260820.csv` | 全量 1,269 列（LIVE 1,259 + REJECTED 10）：npi / effective_npi / customer_id / clinic_id / old_clinic_id / vendor / legacy_emr_service / type / flags / msh06 / clinic_name / updated_at / id |
| `npi-match-blockers-20260820.csv` | 126 筆在新 key 下無法比對的列（缺 NPI / NPI 格式錯 / check digit 錯 / 缺 clinic_id），含 reason |
| `npi-clinic-collisions-20260820.csv` | 312 列 / 151 個 `(npi, clinic_id)` 撞 key 的組合，含 severity 分類 |

## 母體

| 指標 | 值 |
|---|---|
| 全部列 | 1,269（LIVE 1,259、REJECTED 10） |
| LIVE + `ordering_enabled=1`（新規則的真正母體） | **1,154** |
| distinct `customer_npi`（LIVE+ordering） | **889** |
| distinct `clinic_id`（LIVE+ordering） | **553** |
| distinct `customer_npi`（全 LIVE，含 result-only） | 953 |
| 近 90 天真正有送 HL7 order 的 clinic | **36**（712 個 order 檔；120 天 42、180 天 47） |
| 上述 36 家 clinic 底下的 ordering 列 | 176（其中 clinic 17147 佔 44、13505 佔 33） |

> 母體 553 家 vs 實際在送單 36 家：新規則的實務影響面集中在這 36 家，
> 其餘 517 家是歷史/待用整合。migration 驗證應以這 36 家為必過清單。

## Vendor 分布（LIVE + ordering_enabled=1）

| Vendor | 列數 | distinct NPI | clinic 數 | 無 NPI 列 |
|---|---|---|---|---|
| MDHQ(Cerbo) | 387 | 296 | 182 | 2 |
| **(ehr_vendor_id = NULL)** | **221** | 200 | 93 | 3 |
| Practice Fusion | 132 | 91 | 66 | 0 |
| ATHENA | 88 | 58 | 20 | 0 |
| POWER2PRACTICE | 79 | 61 | 51 | 0 |
| OptiMantra | 46 | 44 | 32 | 0 |
| CharmEHR | 41 | 39 | 32 | 0 |
| OptimalDX | 39 | 35 | 36 | 2 |
| ElationEMR | 35 | 35 | 31 | 0 |
| FOLLOWTHATPATIENT | 33 | 21 | 20 | 2 |
| eClinicalWorks | 20 | 19 | 14 | 1 |
| THM | 16 | 16 | 1 | 0 |
| HealthMatters | 4 | 4 | 1 | 0 |
| PraxisEMR | 3 | 3 | 3 | 0 |
| 其餘 10 家各 1 列 | 10 | 10 | 10 | 0 |

⚠ **221 列（19%）`ehr_vendor_id` 是 NULL，且這 221 列的 `legacy_emr_service` 也全部是 NULL**
→ 這批整合的 vendor 身分在 DB 裡完全查不到（只能靠 SFTP 路徑/檔名反推）。
如果新規則要把 vendor 納入 key 或用 vendor 決定 parsing 行為，這 221 列必須先補。

## 新 key `(customer_npi, clinic_id)` 的可用性

### 1. 硬 blocker：126 筆（詳見 blockers CSV）

| 原因 | 筆數 | 備註 |
|---|---|---|
| `customer_npi` NULL/空 | 10 | 含 MDHQ 2、FOLLOWTHATPATIENT 2、OptimalDX 2、eClinicalWorks 1、無 vendor 3。其中 **1 筆屬近 90 天活躍 clinic**（cust 506017 / clinic 12944 / MDHQ） |
| `clinic_id` NULL/0 | 96 | 這批今天也下不了單（parser 對 `clinic_id===0` 就回 `customer_not_found`），但新規則會把它們從「潛在可用」變成「明確不可用」 |
| NPI 非 10 碼數字 | 3 | `IHP`(cust 14829/clinic 136227)、`Internal N`×2（cust 503888/clinic 8093、cust 506855/clinic 14774）— 後者是 gRPC 回傳 "Internal NPI" 被截斷寫進 DB |
| NPI 10 碼但 check digit 不合 | 17 個 NPI | 含明顯假值 `1234567890`、`1000000019`、`1000000074`、`1000000123`、`2019011314`、`2019050611`、`9252019003`、`0000000055`、`1000000000` 等（日期/流水號填充）。目前 code 不驗 check digit，改成 NPI-based matching 前要決定驗不驗 |

### 2. Key 不唯一：151 個 `(npi, clinic_id)` 撞成 312 列

| 分類 | key 數 | 意義 |
|---|---|---|
| 同 customer 重複列 | 130 | 只需要決定性 tie-break（可沿用現行 `FULL > ORDER_ONLY > 其他，再 updated_at desc`） |
| **對到 >1 個 `customer_id`** | **21** | 真正要決策：同一個醫師 NPI 在同一 clinic 有 2 個 VA 帳號，選錯 → 價格/promo/付款方式/result 路由全部跟著錯（VP-17589 那類 5% 折扣就是 customer 層設定） |
| 對到 >1 個 vendor | 9 | 例：`1083747265|121565` eClinicalWorks + MDHQ、`1720030083|72403` Practice Fusion + OptimalDX。若 vendor 影響 parsing/回傳路徑，需要 vendor 也進 key 或明確優先序 |

近 90 天活躍 clinic 內的撞 key：21 個，其中 **5 個對到 2 個 customer_id**，必須在上線前逐一裁定：

| key (npi\|clinic) | customer_id | vendor | type |
|---|---|---|---|
| 1013094069\|17147 | 11733 / 14933 | (null) | ORDER_ONLY |
| 1194003582\|17147 | 11734 / 14942 | (null) | ORDER_ONLY |
| 1518987338\|17147 | 11732 / 14940 | (null) | ORDER_ONLY |
| 1861455032\|17147 | 11740 / 14944 | (null) | ORDER_ONLY |
| 1568599710\|6212 | 5110 / 5356 | MDHQ(Cerbo) | FULL_INTEGRATION / ORDER_ONLY |

其餘 16 個是同 customer 的重複列（clinic 13505 / 17147 為主），tie-break 就夠。

### 3. 跨 clinic 的 NPI：52 個

52 個 NPI 出現在 >1 個 clinic（例 `1073000691` 橫跨 4 家：2930/8003/36290/144510，FOLLOWTHATPATIENT）。
這正是新 key 想解決的情形 —— 加上 clinic_id 後可正確分流；前提是 inbound HL7 真的帶得出 practice_id。

## 最大未知：inbound HL7 的 practice_id 從哪一欄來

- 今天 emr-v2 **唯一**會讀的 clinic 級欄位是 **MSH-4（sending facility）**，只用在
  `hl7-order.processor.resolveIntegration` 的 clinic-level fallback（`customer_id='-1'`），
  且該結果只拿來 logging + 取 provider email，不參與下單。
- `ehr_integrations.msh06_receiving_facility` 是**外送 result** 用的欄位，語意相反，且值本身不一致：
  1,154 筆 ordering 列裡 **667 筆 = customer_id**、僅 **113 筆 = clinic_id**、152 筆 NULL、222 筆兩者都不是。
  → **不能拿 msh06 當 practice_id 的來源或對照**。
- `hl7_file_input.order_input` 存的是解析後的 outbound payload（有 clinic_id，沒有 NPI/MSH），
  所以 **raw MSH-4 的實際填法無法從 DB 統計**，必須抽 SFTP/pod 上留存的原始 HL7 檔，按 vendor 各抽樣確認。
  這是動工前第一件要做的事：若某 vendor 的 MSH-4 沒填或填的不是 clinic_id，新規則對該 vendor 直接失效。

## 建議的動工順序

1. 抽樣近 90 天 36 家活躍 clinic 的原始 HL7，逐 vendor 確認 practice_id 實際落在哪一欄（MSH-4 / ORC-21 / OBR / 其他），統計覆蓋率。
2. 補 10 筆缺 NPI + 3 筆格式錯的列（真值來自 gRPC getCustomer / NPPES）；決定 17 個假 NPI 怎麼處理。
3. 裁定 21 個 multi-customer key（先做活躍的 5 個），其餘 130 個同 customer 重複列沿用現行 tie-break。
4. 決定 vendor 是否進 key；若要，先補 221 筆 NULL vendor。
5. Migration 用 shadow-compare：新舊 key 並行跑一段，比對兩者解出的 customer_id 是否一致（VP-16968 cutover 前的 shadow 模式可複用），差異全部人工看過再切。
