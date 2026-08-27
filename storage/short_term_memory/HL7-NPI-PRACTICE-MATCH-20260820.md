---
id: HL7-NPI-PRACTICE-MATCH-20260820
type: stm
category: emr_integration
status: active
created: 2026-08-20
updated: '2026-08-24'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7FAIL-20260722-MDHQ
- HL7FAIL-20260729-PLESSEN
- HL7FAIL-20260730-TURNPAUGH
- INCIDENT-20260808-critical-result-tnp
- INCIDENT-20260817-onprem-stale-deploy
- INCIDENT-2604156666
- LBS-1541
- LBS-1656
- LIS-7716
- QH-1660
- QH-2257
- QH-2577
- QH-3752
- QH-4350
- QH-4352
- QH-4608
- QH-5840
- RESULTCHECK-20260819-RCODE-2608186060
- VEJO-DELETION-20260804
- VP-14787
- VP-15279
- VP-15952
- VP-16014
- VP-16166
- VP-16175
- VP-16186
- VP-16193
- VP-16251
- VP-16271
- VP-16280
- VP-16329
- VP-16685
- VP-16734
- VP-16765
- VP-16766
- VP-16832
- VP-16881
- VP-16885
- VP-16934
- VP-16987
- VP-17076
- VP-17117
- VP-17120
- VP-17136
- VP-17283
- VP-17286
- VP-17344
- VP-17411
- VP-17460
- VP-17466
- VP-17474
- VP-17475
- VP-17493
- VP-17497
- VP-17499
- VP-17503
- VP-17517
- VP-17524
- VP-17537
- VP-17538
- VP-17539
- VP-17544
- VP-17584
- VP-17589
- VP-17591
- VP-17628
- VP-17631
- VP-17685
- VP-17686
- VP-17691
- VP-17715
- VP-17734
- VP-17748
- VP-17752
- VP-17810
- VP-17812
- VP-17827
- VP-17914
- emr-integration
- fhir-api
relations:
  unblocked_by: []
  blocks: []
  sibling:
  - HL7FAIL-20260730-TURNPAUGH
  - HL7FAIL-20260722-MDHQ
  - VP-17628
unblock_when: 抽樣原始 HL7 確認各 vendor 的 practice_id 實際欄位（MSH-4 或其他）後才能排實作；驗證方式：從 SFTP/pod
  留存檔抽近 90 天 36 家活躍 clinic 的原始 order 檔，逐 vendor 統計 practice 欄位覆蓋率
tags:
- hl7-order-intake
- npi-matching
- practice-id
- ehr-integrations
- inventory
- leo-decision
- prod-evidence
summary: Leo 決定：所有 HL7 inbound order 改用 customer_npi + practice_id(clinic_id) 比對，取代現行
  ORC-12.1 → customer_id。已產出 prod ehr_integrations 全量 NPI×clinic×vendor 盤點（reference/ehr-integrations-npi-clinic-vendor-20260820.*）：1,154
  筆 LIVE+ordering / 889 NPI / 553 clinic，但實際近 90 天只有 36 家 clinic 在送單。新 key 有 126 筆硬
  blocker（10 缺 NPI、96 缺 clinic_id、3 格式錯、17 假 NPI）與 151 個撞 key（21 個對到 2 個 customer_id，5
  個落在活躍 clinic）。最大未知：inbound practice_id 到底在哪一欄——今天只有 MSH-4 被讀且僅供 logging，msh06 欄位是外送
  result 用且 667/1154 存的是 customer_id，不可當對照。實證追加：MDHQ 的 ORC-12 送 NPI（33/33），撞 key 的
  5 筆歷史單全部下給較早的 backfill 列（11733/11740），但那是 row order 的巧合；且 clinic 6212 的 2 筆 2026-08
  單 MSH-4=139134 與我們的 clinic_id=6212 不符，改用 (npi, MSH-4) 會把它們變成 customer_not_found。
score: 0.9893
---

# HL7 order matching 改為 customer_npi + practice_id — 決策記錄與盤點

## Decisions Made

- **2026-08-20 Leo 決定**：後續所有 HL7 inbound order 一律比對 **`customer_npi` + practice_id(`clinic_id`)**，
  取代現行「ORC-12.1 → `≤7碼 fetchById` / 否則 `fetchByNpi` → `ehr_integrations.customer_id`」的比對方式。
  本次交付＝盤點現況，不動 code。
- 前一輪（同日）已確認的背景：`customer_id` 本身是平台契約級硬需求（Place Order API 必填、charging /
  patient / pricing 全部以 customer 為 tenant key），但「用哪個欄位配對到那個 customer」是 emr-v2 自己的
  路由設計，可改 —— 這個決定改的是後者。

## 交付物

- `reference/ehr-integrations-npi-clinic-vendor-20260820.csv` — 全量 1,269 列盤點
- `reference/npi-match-blockers-20260820.csv` — 126 筆新 key 下無法比對的列
- `reference/npi-clinic-collisions-20260820.csv` — 312 列 / 151 個撞 key 組合
- `reference/ehr-integrations-npi-clinic-vendor-20260820.md` — 分析報告（vendor 分布、blocker、撞 key、動工順序）

## 關鍵數字（prod snapshot 2026-08-20）

- LIVE 1,259 列，其中 `ordering_enabled=1` **1,154**；distinct NPI **889**；distinct clinic **553**
- 但近 90 天真正送過 HL7 order 的只有 **36 家 clinic**（712 檔；120 天 42 家、180 天 47 家）→ migration 必過清單
- Vendor：MDHQ 387、**vendor_id NULL 221（legacy_emr_service 也全 NULL，vendor 身分 DB 查不到）**、
  Practice Fusion 132、ATHENA 88、P2P 79、OptiMantra 46、CharmEHR 41、OptimalDX 39、Elation 35、FTP 33…
- Blocker 126：缺 NPI 10（1 筆在活躍 clinic：cust 506017/clinic 12944/MDHQ）、缺 clinic_id 96、
  NPI 非 10 碼 3（`IHP`、`Internal N`×2）、check digit 不合 17 個 NPI（`1234567890`、`0000000055` 等假值）
- 撞 key 151：同 customer 重複 130（tie-break 可解）、**對到 >1 customer_id 21**（活躍的 5 個：
  1013094069/1194003582/1518987338/1861455032 @clinic 17147、1568599710 @clinic 6212）、對到 >1 vendor 9
- 52 個 NPI 跨多 clinic（`1073000691` 跨 4 家）→ 這是新 key 的正當性所在

## Failures / 陷阱（給下一輪的人）

- **`msh06_receiving_facility` 不能當 practice_id 對照**：那是外送 result 的 MSH-6，語意相反；
  1,154 筆裡 667 存的是 customer_id、只有 113 是 clinic_id、152 NULL、222 兩者皆非。
- **raw MSH-4 無法從 DB 統計**：`hl7_file_input.order_input` 是解析後的 outbound payload（有 clinic_id，
  無 NPI/MSH），原始 HL7 只在 SFTP／pod local dir。要確認 practice_id 欄位必須抽原始檔。
- 今天 code 裡唯一讀 clinic 級欄位的地方是 `hl7-order.processor.resolveIntegration`（MSH-4 + `customer_id='-1'`），
  結果只用於 logging 與取 provider email，**不參與下單**；真正下單在 `parser.service.ts:170-194`。
- prod 目前 `customer_id='-1'` 的 clinic-level 列共 36 筆，`ordering_enabled=1` 的 **0 筆** —— clinic-level 下單從未啟用。

## Next（未動工）

1. 抽樣 36 家活躍 clinic 的原始 HL7，逐 vendor 確認 practice_id 欄位與覆蓋率（unblock 條件）
2. 補 13 筆 NPI（10 缺 + 3 格式錯）；決定 17 個假 NPI 的處置
3. 裁定 21 個 multi-customer key（先 5 個活躍的）
4. 決定 vendor 是否進 key；若要，先補 221 筆 NULL vendor
5. Cutover 用 shadow-compare（新舊 key 並行比對解出的 customer_id），差異人工審完再切

## 歷史訂單實證（2026-08-20 追加，Leo 追問「過去發生過嗎、當時下給誰」）

- 證據鏈：on-prem prod pod 歸檔 HL7（33 檔 / clinic 17147+6212+19583）取 MSH-4 + ORC-12
  → AKS prod pod 呼叫 coresamples `SampleService.GetSampleRelevantInfo` 解 sample→customer。
  lis_re/lis_core 的 order_table 從本機與 appserver04 都是 TCP 通、MySQL handshake 逾時，未能使用。
- **MDHQ 的 ORC-12.1 送的是 10 碼 NPI（33/33），不是 customer_id** → 這些單今天就走 `fetchByNpi`，
  撞 key 是現行生產路徑而非假設；MSH-4 帶診所號。
- **撞 key 的單真的來過 5 筆，全部落在同一邊**：NPI 1013094069（Lilli Link）4 筆
  （sample 2537944/2538387/2560139/2564356，2026-04-15..05-22）→ 全部 customer **11733**；
  NPI 1861455032（Jennifer Glassman）1 筆（sample 2592436, 2026-07-08）→ customer **11740**。
  對照組 NPI 1477517258（單一 customer）→ 10820，一致。
  兩個勝者都是 `Parsley Health (4)` 那組（較早的 VP-16968-backfill 列），`Virtual` 那組（14933/14944）一筆都沒拿到。
- **但這個穩定是巧合**：候選兩列 type 同為 ORDER_ONLY 且 `updated_at` 完全相同 → tie-break 退化，
  勝者是 MySQL 先回傳的列（插入順序）。任何人 touch 到 `updated_at` 就會把之後所有單翻到另一個帳號。
- **比撞 key 更嚴重的發現：practice_id 對不上。** clinic 6212 的 2 筆 2026-08 單
  （sample 2615231/2617510）MSH-4=**139134**（MedSomma，customer 50554），ORC-12 NPI=1992777957
  → 實際下給 **customer 38750**，而該 customer 的 ei 列寫 clinic **6212**、coresamples 說她的 clinic 是 **142743**。
  `ehr_integrations` 裡沒有 (1992777957, 139134) 的列 → **改用 (npi, MSH-4) 比對這 2 筆會變成 customer_not_found**，
  今天它們是成功的。MSH-4 語意=送件診所，我們的 clinic_id=provider 帳號綁的診所，同一張單上可以不同。
- 結論修正：建議 **分層 fallback**（ORC-12 解得到就以它為準，(npi, practice) 只當 fallback），
  上線前必做「MSH-4 vs clinic_id vs coresamples clinic」全量對帳；若要收斂資料，
  就把 Parsley 那 2 個 NPI 的 Virtual 列（14933/14944）ordering_enabled 關掉，讓現況變成明文規則。

## 已執行：(NPI, clinic_id) 去重（2026-08-21，Leo 指令 + 三項裁定）

裁定：唯一性取 **(NPI, clinic_id)**（保跨診所 provider，也與 npi+practice 複合 key 一致）；
**有 result 傳送史的列只關 ordering_enabled 不刪**；保留者以**實際有 result 活動的 customer** 為準。

- 備份：`~/src/credential/ehr-integrations-live-npi-backup-20260821.json`（1,211 列，執行前全量）
- 動作清單：`reference/npi-clinic-dedup-plan-20260821.csv`（198 列）
- 執行結果：180 群組 → **DELETE 155 列 / DISABLE 43 列**（42 有 result 史 + 1 掛 onboarding email 寄送紀錄）。
  表 1,270→1,115 列；LIVE+ordering 帶 NPI 1,144→946 列 / 889 NPI / 549 clinic。
  `last_modified_by='hung.l@zymebalanz.com NPI-CLINIC-DEDUP-20260821'`
- **不變量成立**：LIVE + ordering_enabled 中 `(customer_npi, clinic_id)` 重複 = 0（DB 端與 prod pod 端各驗一次）
- Consumer readback（Gate 7）：在 emr-v2 prod pod 內用 pod 自己的 Prisma client 重跑
  resolveOrderingIntegration 的邏輯 —— 4 個原本歧義的 NPI 各只解出 1 列（11733 / 11740 / 8221 / 4317）
- **6 組跨 customer 的路由刻意改變**（依 result 活動）：1134304983|11738 10655→8221（0→60 筆）、
  1457616708|71872 7121→4317（0→195）、1669482139|132145 30177→30111（6→277）、
  1245828383|149877 46332→47629（2→60）、1487999850|15956 7163→10335（0→3）、
  1639180516|NULL 1974→1968（5→6）。其餘 36 組是同 customer 換列，無路由變化。
- 38 個 customer 從此沒有 ordering-enabled 列（重複帳號，含 Parsley Virtual 的 14933/14940/14942/14944）；
  其中 17 列刪除後該 customer 也不再有 result-capable 列，但這 17 個 customer 的 rtr 量全部為 0（休眠帳號）。

### 待決（未動）：15 組「NULL clinic + 真 clinic」配對
`clinic_id IS NULL` 與正常列分屬不同群組所以沒被去重，且 `resolveOrderingIntegration` 不過濾 clinic
→ NULL 列若贏 tie-break，parser 會因 clinic_id=0 判 customer_not_found（訂單失敗，不只是冗餘）。
LIVE+ordering 仍有 59 列 clinic_id NULL/0。其中 1295025658 / 1427076488 / 1679508675 的 NULL 列是
FULL_INTEGRATION，會贏過真 clinic 的 ORDER_ONLY 列 → 這些 NPI 的單今天應該就是失敗的。
選項：照同一套政策處理，或先補 clinic_id（若是漏填而非重複）。等 Leo。

## 2026-08-21 session 總結（Leo 要在 clear 後檢討流程，材料留在這）

### 已執行的 prod 變更（4 次，全部有備份）

| # | 動作 | 範圍 | 備份 |
|---|---|---|---|
| 1 | `(customer_npi, clinic_id)` 去重 | DELETE 155 列 + DISABLE 43 列（180 群組） | `~/src/credential/ehr-integrations-live-npi-backup-20260821.json` |
| 2 | 停用永遠無法通過 clinic 檢查的 ordering 列 | 59 列 `ordering_enabled=0`（clinic_id NULL/0） | `~/src/credential/null-clinic-disable-backup-20260821.json` |
| 3 | 修正 2 個「勝者不是實際在下單的帳號」 | 停用 12191@56132（NPI 1184178089）、21174@123597（NPI 1336296599） | `~/src/credential/winner-fix-backup-20260821.json` |
| 4 | （無）歷史訂單歸屬**未動** — Leo 指令：不搬單 | — | — |

結果：LIVE+ordering 列 1,144 → **895**；LIVE+ordering 中 `(npi, clinic)` 唯一；
`clinic_id` NULL/0 的 ordering 列 = 0；每個 consumer readback 都在 prod pod 內用 pod 自己的 Prisma 驗過。

### 交付物（全部在 `reference/`，已 push）
- `npi-customer-clinic-vendor.csv`(895) / `-all-live.csv`(1,104) — 基礎盤點
- `npi-customer-clinic-vendor-order-proven.csv`(160) — 排除 RESULT_ONLY + 該帳號真的下過單
- `npi-customer-clinic-vendor-customerid-ordering.csv`(32) — 唯一用 customer_id 下單的 vendor（FollowThatPatient）
- `pm-handoff-followthatpatient-20260821.md` — PM 議題單
- `orders-to-rebook-20260821.csv`(20) — 誤記帳號/診所的訂單（**決定不搬**，僅留紀錄）
- `order-routing-nondeterminism-20260821.csv`(37)、`same-npi-multiple-ordering-customers-20260821.csv`、
  `order-routing-flips-observed-20260821.csv`、`hl7-practice-field-by-vendor-20260821.csv`、
  `npi-clinic-dedup-plan-20260821.csv`、`npi-match-blockers-20260821.csv`、`npi-unique-cost-20260821.csv`

### 還沒解決的（唯一會重複發生的案例）
FollowThatPatient 的 `cust 43262`（Anna Emanuel）一個帳號掛 4 個 clinic（2930/8003/36290/144510）→
每一筆不是 2930 的單都會被掛到 2930（已確認誤送 sample 2597376）。資料層無解，兩條路：
拆成每 location 一個帳號（PM 單），或 emr-v2 改讀 `ORC-17`/`MSH-6`（他們已經在送）。

### 流程問題（我的，供檢討）
1. **順序錯**：先跑了資料收斂（變更 1），才確認 `resolveOrderingIntegration` 不看 clinic、
   以及各 vendor 實際送哪個識別碼。應該先建立「比對行為 + vendor 送什麼」的事實基礎再談動資料。
2. **論證用錯指標**：用「這個 clinic 有沒有下過單」論證「零代價」，被 Leo 當場反駁——
   停用一列不會讓那家診所退件，會靜默改掛到別家。正確指標是「該 customer 帳號有沒有下過單」。
3. **把條件句當結論**：「practice_id 進 key 就全部歸零」在我們還沒比對 practice 的前提下是計畫、不是現況，
   被 Leo 指出。
4. **歸因錯誤**：說 13 筆誤記是「我們自己的比對翻掉」，查 `last_update_pod_name` 後 12 筆屬 legacy Java v1 時代。
   結論前應先確認是哪個引擎處理的。
5. **交付格式來回**：Leo 要 CSV，我持續交 md；CSV 的篩選條件（排除 RESULT_ONLY、限真的用過 customer_id）
   讓他講了三次才收斂。**要什麼格式先問清楚，不要用 md 代替 csv。**
6. **技術性浪費**：raw HL7 讀取踩了兩次坑——awk 欄位偏移（ORC-12 在 `$13` 不是 `$12`，因為 segment name 占 `$1`）、
   FTP 的檔案是 CR 分隔（要 `tr '\r' '\n'`）。expect 的 `timeout 60` 也讓一次全量掃描被截斷成部分結果。

### 這次驗證方法上值得保留的
- **原始 HL7 是唯一 ground truth**：欄位語意（ORC-12 是 NPI 還是 customer_id、診所在 MSH-4/MSH-6/ORC-17）
  只能從 pod 上的歸檔檔確認，DB 裡的 `order_input` 是解析後的 outbound payload。
- **sample → customer 用 coresamples `GetSampleRelevantInfo`**（5,352 筆全解、0 錯誤）；
  customer → NPI 用 `GetCustomer`；customer → clinic 清單用 `ListCustomerAllClinics`（會回 30+ 個，證明
  provider↔clinic 是多對多，「這個 customer 的 clinic」沒有唯一答案）。
- **引擎歸因看 `hl7_file_input.last_update_pod_name`**：`lis-emr-prod-*` = legacy Java v1、
  `lis-emr-v2-deployment-*` = emr-v2。

## 2026-08-24 流程檢討（Leo review 定案 — transcript 驗證過）

Leo 的假設：「提出很多方案但答不到點上，因為我不清楚（或忘記）『有人用 customer_id 下單、
且我們一直是這樣判斷』」。回放 08-20/08-21 兩個 session（40a8c033 / 91b48a51）後**成立**，精確形狀：

- **不是 agent 不知道，是 agent 沒講。** `ORC-12.1 ≤7碼 → fetchById(customer_id) / 否則 fetchByNpi`
  從 08-20 就寫在本 STM，但第一份盤點交付（08-20 18:19）完全沒有現況段落——「取代今天的
  ORC-12.1 → customer_id 比對」只以括號註記埋在報告 md 開頭。完整模型直到 08-21 22:37
  （Leo 強制要求「以 1366420523 從頭講一次流程」）才第一次出現，開工約 28 小時後。
- **量化損失**：至少 7 個 turn 是 Leo 在補課現行機制（08-20 18:26/18:30、08-21 22:19/22:25/
  22:32/22:34/22:58「不是..」）；21:57 的去重指令是在不完整模型（NPI 中心）上下的，agent
  照單全收沒有 push back「先確認 customer_id 路徑與各 vendor 送什麼」——這是流程問題 #1
  （順序錯）的真正根源：agent 讓 Leo 也在錯的順序上做決策。
- **事後查證的邊界**：真的送 customer_id 的只有 FollowThatPatient（180 天 4 筆）；Leo 22:58
  設計的測試（同 NPI 出現在多個 customer 帳號，6 例）跑出來全部是 NPI 下單，翻帳號是
  tie-break/legacy 造成——該推論線是負結果。customer_id 問題的真實形狀只有 43262 跨 4 clinic。
- **修法（已定案）**：任何「改比對／路由規則」的討論，交付物 #1 = 一頁現況 baseline
  （現行比對輸入欄位與分支＋每條路徑今天誰在走（原始 HL7 驗證）＋tie-break＋輸出欄位），
  且必須出現在給 Leo 的訊息裡、不是埋在報告檔。已寫入 `lis-prod-change-gate` Gate 1
  （擴大觸發範圍到規則討論與資料收斂），walk PR。
