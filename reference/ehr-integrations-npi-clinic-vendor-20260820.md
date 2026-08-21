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

---

# 追加：歷史訂單實證（2026-08-20，Leo 追問「過去發生過嗎、當時下給誰」）

## 證據來源
- 原始 HL7：on-prem prod pod `lis-emr-v2-deployment-prod-84755f45cf-dbxtm` 的
  `/EMR_storage/HL7Message_prod/MDHQ/Prod/Order{,Archive}/`，抽出 3 個撞 key clinic（17147 / 6212 / 19583）
  全部 33 個歸檔訂單檔的 **MSH-4 + ORC-12**。
- sample → customer：從 AKS prod pod 呼叫 coresamples v2 `SampleService.GetSampleRelevantInfo`。
- lis_re / lis_core 的 order_table 從本機與 appserver04 都連得上 TCP 但 MySQL handshake 逾時，未能使用。

## 事實 1：MDHQ 送的是 NPI，不是 customer_id
33/33 個檔案的 ORC-12.1 都是 10 碼 NPI（例 `1962723643^HUMMEL^DEBRA^^^^^N`），
所以這些單**今天就走 `fetchByNpi`** → gRPC NPI→customerIds → `resolveOrderingIntegration` 挑列。
撞 key 的路徑不是假設，是現行生產路徑。MSH-4 則帶診所號（Parsley 全部 = 17147）。

## 事實 2：撞 key 的單真的來過，而且都落在同一邊

| sample | 收單時間 | ORC-12 NPI | 候選 customer | **實際下給** |
|---|---|---|---|---|
| 2537944 | 2026-04-15 | 1013094069 Lilli Link | 11733 / 14933 | **11733** |
| 2538387 | 2026-04-16 | 1013094069 | 11733 / 14933 | **11733** |
| 2560139 | 2026-05-18 | 1013094069 | 11733 / 14933 | **11733** |
| 2564356 | 2026-05-22 | 1013094069 | 11733 / 14933 | **11733** |
| 2592436 | 2026-07-08 | 1861455032 Jennifer Glassman | 11740 / 14944 | **11740** |
| 2583691（對照，單一 customer） | 2026-06-23 | 1477517258 Liz Zapp | 10820 | 10820 ✔ |

5/5 都落在 `Parsley Health (4)` 那組（11733 / 11740，較早建立的 VP-16968-backfill 列），
沒有一筆落在 `Parsley Health Virtual/Complete Care Anywhere`（14933 / 14944）。

**但這個穩定是巧合**：兩列 `integration_type` 同為 ORDER_ONLY、`updated_at` 完全相同，
tie-break（type → updated_at desc）在此退化，勝者是 MySQL 先回傳的那列（插入順序 → 較舊的 id）。
沒有任何規則保證這件事——只要有人 touch 到其中一列的 `updated_at`，之後所有單就會翻到另一個帳號。

## 事實 3：更嚴重的是 practice_id 對不上（不是撞 key）

clinic 6212 的兩筆單（sample 2615231 @2026-08-12、2617510 @2026-08-17）：

| 來源 | 值 |
|---|---|
| HL7 MSH-4（送件診所） | **139134** = MedSomma Regenerative Wellness（customer 50554、NPI 1508438136） |
| HL7 ORC-12 NPI | 1992777957 Carrie Carda → 實際下給 **customer 38750** |
| 我們 `ehr_integrations` 記的 clinic | **6212**（Innovative Health and Wellness Group） |
| coresamples 說 customer 38750 的 clinic | **142743** |

四個號碼互不相符，而 `ehr_integrations` 裡 **沒有任何 (NPI 1992777957, clinic 139134) 的列**
（139134 只屬於另一個 provider 50554）。也就是說：

> 若改用 `(customer_npi, MSH-4)` 比對，這 2 筆 2026-08 月的單會直接被拒成 `customer_not_found`。
> 它們今天是成功的。

MSH-4 的語意是「送件的診所」，我們的 `clinic_id` 記的是「該 provider 帳號綁的診所」，
同一張單上這兩者可以不同 —— 這是新規則最大的實際風險，比撞 key 嚴重。

## 因此建議（更新）

1. **不要用 (npi, practice) 取代現行比對，改成分層**：ORC-12 解得到就以它為準，
   `(npi, practice)` 只當 fallback。這樣既補上 `customer_not_found` 的洞，又不會退化任何現行成功路徑。
2. 上線前必做全量對帳：近 90 天 36 家活躍 clinic 的原始 HL7，逐筆比對 MSH-4 vs 我們的 `clinic_id`
   vs coresamples 的 clinic list，量化「對不上」的比例。上面 2/2 筆 medsomma 已經是對不上的實例。
3. 21 個 multi-customer key 中，實際來過單的只有 Parsley 的 2 個 NPI（5 筆單），
   歷史答案是 11733 / 11740。若要收斂資料，就把這兩個 NPI 的 `Virtual` 列（14933/14944）
   `ordering_enabled` 關掉，讓現況變成明文規則，而不是靠 row order。

---

# 已執行：(NPI, clinic_id) 去重（2026-08-21）

Leo 裁定三件事後執行：唯一性範圍取 **(NPI, clinic_id)**（保留跨診所 provider）；
**有 result 傳送史的列只關 `ordering_enabled`、不刪**；保留者以**實際有 result 活動的 customer** 為準。

- 備份（執行前全量）：`~/src/credential/ehr-integrations-live-npi-backup-20260821.json`（1,211 列，所有 LIVE 帶 NPI 的列）
- 動作清單：`reference/npi-clinic-dedup-plan-20260821.csv`（198 列，含每列的 keep_id / rtr 量 / 判斷依據）

| 項目 | 值 |
|---|---|
| 處理的 (NPI, clinic) 群組 | 180 |
| **DELETE** | **155 列**（無自身 result 傳送史） |
| **DISABLE**（`ordering_enabled=0`，列保留） | **43 列**（42 列有自身 result 傳送史 + 1 列 `cmmcb6x79002kyn07hbf6ehb2` 掛著 3 筆 onboarding email 寄送紀錄，不刪以保 audit trail） |
| 表總列數 | 1,270 → 1,115（−155） |
| LIVE + ordering 帶 NPI 的列 | 1,144 → **946**；distinct NPI 889；clinic 549 |
| 保留者與「原本行為」不同的群組 | 42（其中 36 組是同 customer 的換列，無路由變化；**6 組是跨 customer**，見下） |
| `last_modified_by` 標記 | `hung.l@zymebalanz.com NPI-CLINIC-DEDUP-20260821` |

## 6 組跨 customer 的路由變更（刻意，依「result 活動」準則）

| NPI \| clinic | 原本會走到 | 改為 | 依據（result 傳送筆數） |
|---|---|---|---|
| 1134304983 \| 11738 | 10655 | **8221** | 0 → 60 |
| 1457616708 \| 71872 | 7121 | **4317** | 0 → 195 |
| 1669482139 \| 132145 | 30177 | **30111** | 6 → 277 |
| 1245828383 \| 149877 | 46332 | **47629** | 2 → 60 |
| 1487999850 \| 15956 | 7163 | **10335** | 0 → 3 |
| 1639180516 \| (clinic NULL) | 1974 | **1968** | 5 → 6 |

Parsley 的 4 個 NPI 維持實測歷史結果（11733 / 11740 / 10820 保留，`Virtual` 那組的 14933/14940/14942/14944 移除）。

## 驗證（100%，非抽查）

- 刪除的 155 個 id：`SELECT` 回 0 筆存在
- 停用的 43 個 id：43/43 為 `ordering_enabled=0` 且 `status='LIVE'`
- 不變量：LIVE + ordering 中 `(customer_npi, clinic_id)` 重複 = **0**
- 反向稽核（更寬條件）：仍有 52 個 NPI 落在 >1 個 ordering 列 —— 全部是**跨診所的同一位醫師**（預期保留），
  其中 15 個是「一列 clinic_id 為 NULL + 一列有真 clinic」的配對，見下方待決事項
- Consumer-layer readback：在 emr-v2 **prod pod 內**用 pod 自己的 Prisma client 重跑，
  duplicates=0、946 列，且 4 個原本歧義的 NPI 各自只解出 1 個候選列
  （11733 / 11740 / 8221 / 4317），與預期一致

## 待決：15 組「NULL clinic + 真 clinic」配對（未動）

`clinic_id IS NULL` 的列與同 NPI 的正常列分屬不同群組，所以沒被去重。這批不只是冗餘 ——
`resolveOrderingIntegration` **不過濾 clinic**，NULL-clinic 列若贏了 tie-break，parser 會因
`clinic_id=0` 直接判 `customer_not_found`，訂單失敗。目前 LIVE+ordering 仍有 **59 列** clinic_id 為 NULL/0。

15 組配對（左＝有真 clinic，右＝NULL）：1003336108 / 1023218161 / 1083900310 / 1124183017 /
1144288861 / 1285925735 / 1295025658 / 1427076488 / 1548367923 / 1558520965 / 1629059274 /
1629512744 / 1669482139 / 1679508675 / 1790723013。

其中 1295025658、1427076488、1679508675 的 NULL 列是 `FULL_INTEGRATION`，會**贏過**真 clinic 的
`ORDER_ONLY` 列 → 這些 NPI 的單今天應該是失敗的。要按同一套政策處理（有 result 史→停用、否則刪），
還是先補 `clinic_id`（若那是設定漏填而非重複），需要 Leo 決定。
