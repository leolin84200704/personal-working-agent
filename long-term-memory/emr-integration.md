---
id: emr-integration
type: ltm
category: emr_integration
status: active
score: 1.0147
base_weight: 1.0
created: 2026-04-22
updated: 2026-07-22
links:
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7-TRIAGE-20260427
- HL7FAIL-20260722-MDHQ
- INCIDENT-2604156666
- LBS-1541
- LBS-1656
- QH-1660
- QH-2257
- QH-2577
- QH-3752
- QH-4350
- QH-4352
- QH-4608
- QH-5840
- VP-14787
- VP-15279
- VP-15952
- VP-16014
- VP-16157
- VP-16166
- VP-16175
- VP-16180
- VP-16186
- VP-16193
- VP-16233
- VP-16245
- VP-16251
- VP-16271
- VP-16280
- VP-16289
- VP-16329
- VP-16379
- VP-16396
- VP-16423
- VP-16424
- VP-16463
- VP-16476
- VP-16617
- VP-16685
- VP-16720
- VP-16734
- VP-16765
- VP-16766
- VP-16784-87
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
- VP-17517
- fhir-api
tags:
- emr
- hl7
- integration
- provider
- practice
- hl7_file_input
- triage
- order-api
- payment
summary: EMR/HL7/SFTP integration rules, identity mapping, MSH values, bundle config,
  hl7_file_input triage
---



































































































# EMR Integration Rules

> Single source of truth. Consolidated from VP-15874, VP-15979, VP-15791, VP-15980, VP-15955.
> **FHIR / 新 API 版本 / non-SFTP inbound order 前門相關 → 見 [[fhir-api]]**（HL7v2↔FHIR 比較、reuse map、難度排序、Epic/Story/Ticket 拆解）。

---

## Identity Mapping

| 概念 | 來源 | 映射到 |
|------|------|--------|
| Provider ID | Ticket | `ehr_integrations.customer_id`, `order_clients.customer_id` |
| Practice ID | Ticket | `order_clients.clinic_id`（**不是** customer_id！）|
| Provider Name | **gRPC 必查** | `order_clients.customer_name`（不是 ticket 裡的 clinic name）|
| Clinic Name | Ticket | `ehr_integrations.clinic_name`, `order_clients.customer_practice_name` |
| NPI | **gRPC 必查** | `order_clients.customer_provider_NPI` |

- **Provider ID ≠ Practice ID** — 永遠不要搞混
- gRPC endpoint: `192.168.60.6:30276`, Script: `scripts/get-customer-rpc.ts`
- **不要從 ticket 猜測 provider-clinic 關係**，gRPC 回傳的 clinics 陣列才是正確的
- **gRPC GetCustomer 是 customer 資料的唯一權威來源** — `crm.contacts` 只有部分 customer（約 53%），不可靠
- Standalone script 呼叫 gRPC 見 `patterns.md` → "gRPC from Standalone Scripts"

---

## MSH Value 判定

- **新預設（2026-04-23 起）**：`msh06_receiving_facility` = **Practice ID**（clinic_id）
- **原因**：Kristine 在 VP-16280 comment 確認「Practice IDs as MSH, all customers moving forward — EMR vendors recognize integrations at practice-level and usually require one MSH per practice」
- **歷史資料**：既有舊 integration MSH 多為 Provider ID，未必回填；bulk update 需獨立 ticket 用 `update-clinic-msh.ts`
- **BULK UPDATE**：ticket 寫 "update ALL MSH values" → 用 `update-clinic-msh.ts`
- **Practice-wide alignment**: 當新 ticket 是「add-provider」且 same-practice 既有 MSH 還停留在 Provider ID 時，Leo 傾向一次把該 practice 全部既有 record 也改成 Practice ID，保持一致。Plan 階段主動把這點列為決策點，不要預設「只改新的」
- **Ticket 處理前重新拉 Jira comments** — STM 的 ticket analysis 可能過時，PM 後續留言可能改變需求（如 VP-16379 後補 Provider ID）
- **PM 轉述 vendor 回覆的 folder/縮寫要 sanity-check 與 practice 名稱對應** — 不能照單全收。VP-16245 case：ticket description 寫 `/awc`（Alpine Wellness Clinic = AWC，合理），Kristine 4/28 留言「Cerbo confirmed that we should use /acw」，當時採用 /acw 寫進 prod DB。5/4 Leo 親查 SFTP server 確認實際是 /awc，已 rollback。當縮寫與 practice 名稱明顯不對應時（ACW 對 Alpine Wellness Clinic）主動回 PM 再跟 vendor 確認，不要照單全收。

---

## Integration Type Rules

| Type | order_clients 需要？ | update-order-clients flag |
|------|---------------------|--------------------------|
| FULL_INTEGRATION | Yes | true |
| RESULT_ONLY | No | false |
| ORDER_ONLY | Yes | true |

- **ticket 未指定 integration type = FULL_INTEGRATION（預設）**
- FULL_INTEGRATION 需要 order_clients + sftp_folder_mapping
- **integration_type 不 follow 既有 same-practice integration** — 即使該 practice 既有 provider 都是 RESULT_ONLY，新 provider 仍套用預設 FULL_INTEGRATION
- **唯一例外**：該 vendor 本身只提供 result-only 服務時，才用 RESULT_ONLY

### capability flag ↔ integration_type 推導 + 「啟用 flag = 啟用一條 pipeline」（VP-16968 教訓）
- emr-v2 的 `ehr_integrations` 三個 flag 與 `integration_type` 在 create/update（auto-integrate API）原本**完全獨立**、純由 request body 的 `technicalRequirements` 決定（DTO + Prisma 雙層 default 全 false），不從 type 推導、無 validation → 「請求通過 ≠ integrate 成功」。VP-16968 加 `deriveCapabilityFlags`（`integration-type-validation.util.ts`）依 type 推導：**ORDER_ONLY**(o1,r0,s1) / **RESULT_ONLY**(o0,r1,s1) / **FULL_INTEGRATION**(o1,r1,s1) / **OTHER**(只 s1)。`sftp_enabled` 一律手動/預設 true。
- 下游真正的 gate 是 flag 不是 type：order → `ordering_enabled=true`（`hl7-order.processor.ts`）；result 生成 → `result_enabled OR type∈{RESULT_ONLY,FULL}`；Kafka result → `result_enabled AND type`；sftp → `sftp_enabled`。
- **鐵則：set/backfill 一個 capability flag 前，逐一確認該 flag 啟用的下游 pipeline 有足夠 config 支撐**。VP-16968 翻車案例：把 225 純 order 來源列 backfill 成 `FULL_INTEGRATION + result_enabled=1`，但它們沒有任何 result config（ehr_vendor_id / sftp_result_path / sftp_host / msh06 全 null）→ 報告完成時會被 result pipeline 選中然後失敗。**啟用一個 capability = 啟用一條 pipeline**；result_enabled 需要 vendor/sftp_result_path，ordering_enabled 需要 order 解析來源。修正為 ORDER_ONLY(o1,r0,s1) 後零回歸（這批客戶在 `result_transmission_records` 從未以 result_client_id 出現過 → 從沒走 result pipeline）。

### Order 解析來源：order_clients → ehr_integrations cutover（VP-16968）
- 舊路徑 order 准入閘門 = `order_clients`（`customer-detail-fetcher.service.ts` fetchById/fetchByNpi，覆寫 kits_options/clinic_id/old_clinic_id；customer 主檔來自 gRPC GetCustomer）；`hl7-order.processor.ts` 查 ehr_integrations 只做 logging（Java parity，配不到不擋）。
- VP-16968 cutover：閘門改 `ehr_integrations`，gate = **status='LIVE' AND ordering_enabled=true**；多列優先序 **FULL > ORDER_ONLY > 其他，再 updated_at desc**；`kits_options` / `old_clinic_id`（order payload/token 必要，原來只在 order_clients）新增到 ehr_integrations 欄位並從那取。
- 前置陷阱：`order_clients` 955 distinct 客戶中 ~225（23.6%）**完全沒有 ehr_integrations 列** → 直接 cutover 會停單，必須先 backfill。`order_clients` 是 per-customer（非 per (customer,clinic)），多列衝突時 Java findFirst 取第一筆。
- **VP-16968 後新整合只寫 `ehr_integrations`，不碰 `order_clients`**（kits_options/old_clinic_id 已在 ehr_integrations 欄位）。Leo 明確：order_clients 現在完全不碰。

### inbound order 解析的 key = ORC-12.1，**不是 MSH-6**（VP-17136 釐清，務必記住）
- **真正決定「誰下單」的是 `ORC-12.1`**（ordering provider）：parser.service 取值，`len<=7 → fetchById(customer_id)` 否則 `fetchByNpi(NPI)`。`customer-detail-fetcher` 兩條路最終都用 **customer_id** 去 `ehr_integrations`(LIVE+ordering) 配對（fetchByNpi 先 gRPC `getCustomerByNPINumber` 把 NPI→customerIds，再 by customer_id 配）。
- **`ehr_integrations.customer_npi` 在 order 路徑其實不被直接配對用**（matching 靠 customer_id）→ 無 NPI 帳號（如 Practice Admin，gRPC 回 "Internal NPI"）只要 customer_id 有 LIVE+ordering 列、FTP 在 ORC-12 送該 **customer_id（≤7碼走 fetchById）** 就能下單，customer_npi 留 NULL（clinic-level）即可。
- **inbound order 的 MSH-6（receiving facility）emr-v2 完全不用**。MSH-6 語意=收件方(Vibrant 實驗室)；`ehr_integrations.msh06_receiving_facility` 是給**外送 result** 用的 MSH-6（hl7-encoder），與 inbound order 的 MSH-6 是**相反方向、不同東西**。
- **MSH-4（sending facility）** 只在 `hl7-order.processor.resolveIntegration` 的 clinic-level fallback（`customer_id='-1'`=`CLINIC_LEVEL_MARKER` AND `clinic_id=MSH-4`）才用；該 processor 解析主供 logging + gz_ny pilot gate，真正下單 fall through 到 parser.service（ORC-12）。
- 教 EMR vendor 填單：強調 **ORC-12=Provider ID(customer_id)**；別說「MSH-6=Practice ID」（誤導）。

---

## Known Script Bugs

### insert-order-client.ts
- **Bug**: customer_id 會被設為 clinic_id 值（Practice ID）而非 Provider ID
- **影響**: order_clients.customer_id 錯誤
- **Workaround**: 執行後必須驗證 customer_id，錯誤時手動 SQL 修正:
  `UPDATE order_clients SET customer_id = {provider_id} WHERE id = {record_id}`

### insert-ehr-integration.ts NPI duplicate 對 same-person/multi-customer-id 不友善
- order_clients duplicate 檢查 key 是 `(customer_provider_NPI, clinic_id)`（不是 `customer_id + clinic_id + vendor`）
- 同人不同 customer_id（例：VP-16423 的 18155 / 25467 都是 KATHERINE KELLER NPI 1356634760）會在第二筆被 throw `Duplicate order_client exists for NPI '...' + clinic_id '...'`
- **這個 throw 會 rollback 整個 prisma.$transaction，包括 ehr_integrations INSERT** — 第二筆 ehr_integrations 也不會留下
- **Workaround**: 提早在 ticket analysis 時掃同 ticket provider list 找 same-NPI duplicate；對「第二筆」改用 raw SQL：
  - `import cuid from 'cuid'; const id = cuid()` 自生 ehr_integrations.id
  - 仿造 same-clinic 既有 LIVE record 的全欄位（sftp_host=34.199.194.51, sftp_port=2210 for MDHQ 等）
  - 直接 INSERT order_clients（繞 NPI duplicate check）
  - 補 ehr_integration_status_history(NULL → LIVE, changed_by=ticket_id, reason 註明 same-NPI duplicate)
- 範例 transaction: VP-16423 `_apply-vp16423.ts`

### insert-ehr-integration.ts
- 當 DB 已有相同 customer_id 的記錄時（如 PENDING 狀態），script 會拒絕插入
- **Unique constraint**: (customer_id, clinic_id, ehr_vendor_id)。同 customer 跨 clinic 可，同 clinic 重複 customer 擋下；ticket 列的 provider 跟 DB 既有重疊時走 UPDATE 不是 INSERT
- **Workaround**: 改用 Prisma update 或 raw SQL 更新現有記錄
- Script 需要 ehr_vendors 中存在 vendor code，新 vendor 必須先加入 ehr_vendors 才能使用
- **MDHQ 已知問題**: `sftp_ordering_path` 不會被設定（null）、`sftp_archive_path` 缺尾部 `/`、`sftp_folder_mapping.sftp_source_id` 為 null — 每次需手動修正
- **判讀執行結果用 grep `Successfully|Error|❌|✅`**，不要用 tail 截取 — record dump 會蓋掉 success 訊息，誤判會重跑撞 unique constraint
- **status 陷阱**（VP-16175 教訓）：`ehr_integrations.status` Prisma schema `@default(PENDING)`，script 必須**顯式**傳 `status=LIVE` 否則落 default。enum: PENDING / APPROVED / LIVE / REJECTED。**第一筆 INSERT 跟後面 6 筆參數可能不同**（CLI 第一次跑漏 flag，Leo 中途糾正後才補），驗證一定要逐 row 看 status，不能 spot check。VP-16175 1/7 stuck PENDING 33 天才被發現
- **驗證 SQL 模板**（每張 ticket 跑完都用、讀每一 row）：
  ```sql
  SELECT customer_id, status, integration_type, ehr_vendor_id, clinic_id, created_at
  FROM ehr_integrations
  WHERE customer_id IN (...ticket 列出全部...) AND clinic_id = {practice_id}
  ORDER BY customer_id;
  ```

---

## Same Practice — Follow Existing Integration

同 practice 新增 provider 時，下列欄位**必須抄 same-clinic 既有 integration 的值**（不是 knowledge 預設）：

| 欄位 | 所在 table | 預設（fallback） | 備註 |
|------|-----------|------------------|------|
| `report_option` | `ehr_integrations` | `PERSONALIZED` | script 已自動處理（`getReportOption(clinicId)`） |
| `kit_delivery_option` | `ehr_integrations` | 對齊 `order_clients.kits_options`（見下方規則） | **script 未處理，需手動補** |
| `old_clinic_id` | `order_clients` | `null` | **script 未處理，需手動補**；同 clinic 的既有記錄通常共用同一個 legacy clinic id |

### kit_delivery_option 對齊規則（VP-16476 修正版）

`ehr_integrations.kit_delivery_option` 是 informational 偏好欄位（auto-integrate module 的 PRD 表單），lis-backend-emr-v2 runtime 完全不 consume；EMR-Backend Java 看的是 `order_clients.kits_options`。對齊規則應該按 ParseHL7 真實語意推算，**不是按 enum 字面語意推測**。

**正確對應**（來源：`EMR-Backend/.../ParseHL7.java:930` switch case）：

| `order_clients.kits_options` | ParseHL7 行為 | `ehr_integrations.kit_delivery_option` |
|---|---|---|
| 0 | non→ship, blood→supplied | `NON_BLOOD_ONLY` |
| 1 | both→ship | `BOTH_BLOOD_AND_NON_BLOOD` |
| 2 | both→supplied | `NO_DELIVERY` |
| 無對應 order_clients（RESULT_ONLY 等）| — | `NO_DELIVERY`（fallback）|

- **Schema default**（VP-16476 起）：`@default(NO_DELIVERY)`（從 BOTH_BLOOD_AND_NON_BLOOD 改）。新 INSERT 不帶 explicit value 會落 NO_DELIVERY。
- **service-layer fallback 也是 NO_DELIVERY**：`integration-request.service.ts:125` `kit_delivery_option: createDto.technicalRequirements.kitDeliveryOption || 'NO_DELIVERY'`
- **VP-16476 全表 backfill 已完成**（2026-05-06）：1015 筆 ehr_integrations 全部按 LEFT JOIN order_clients 重設。Post-distribution: NON_BLOOD_ONLY 668 / BOTH 119 / NO_DELIVERY 228。
- **VP-16423 舊對應表錯了**（`0↔NO_DELIVERY, 1↔BOTH, 2↔未明`）— 是按 enum 字面 + prod 「default 沿用沒覆蓋」配對推出來的，不符合 ParseHL7 真實 runtime 行為。寫入新 ticket 用上面修正版。
- **PENDING stub 不算 same-clinic 既有可 follow** — auto-integrate / admin-portal 預建的 stub 多半 business/technical 欄位全空，`kit_delivery_option` 是 schema default 進來，不是真實設定。判斷「same-clinic 既有」時要看 `status='LIVE'` 且 business 欄位有實質值的 record

```sql
-- 一次撈齊所有 follow-existing 欄位
SELECT report_option, kit_delivery_option FROM ehr_integrations WHERE clinic_id = {practice_id} LIMIT 1;
SELECT old_clinic_id FROM order_clients WHERE clinic_id = {practice_id} AND old_clinic_id IS NOT NULL LIMIT 1;
```

- 若 same-clinic 無既有 → 套上表 fallback
- **注意**: `integration_type` **不** follow 既有，仍套預設 FULL_INTEGRATION（見「Integration Type Rules」）

- **`sftp_folder_mapping` 可能已存在**: 同 practice 的其他 provider 若先建過 integration，ORDER mapping 通常已經在 `sftp_folder_mapping`，insert script 會直接跳過。新增 provider 前先查，避免誤以為 script 失敗。

- **Step 5a probe 必查**：ticket provider 列表 vs DB 既有 customer_id 交集（`SELECT ... WHERE customer_id IN (ticket-list) AND clinic_id = {practice}`）。VP-16329 證實 ticket 列出的 provider 可能已存在 RESULT_ONLY；重疊者走 UPDATE。

- **Practice-wide alignment 是穩定 pattern（VP-16280, VP-16329, VP-16245 連續驗證）**：same-practice add-provider 且既有為 RESULT_ONLY + MSH/archive_path 不一致時，預設一次升級全 practice 為 FULL_INTEGRATION + MSH=Practice ID + archive_path 統一 `/{folder}/results/archive/`。Plan 階段直接列為預設動作，不再當例外。

### MDHQ 升級 RESULT_ONLY → FULL_INTEGRATION 標準動作清單

升級單一既有 record（不 add provider）時的固定 checklist（VP-16245 / VP-16396 連續驗證）：

1. `ehr_integrations.integration_type` RESULT_ONLY → FULL_INTEGRATION
2. `ehr_integrations.ordering_enabled` 0 → 1
3. `ehr_integrations.msh06_receiving_facility` Provider ID → Practice ID（若還沒對齊）
4. `ehr_integrations.sftp_archive_path` → `/{folder}/results/archive/`（修正路徑 + 補尾 `/`）
5. `ehr_integrations.sftp_ordering_path` null → `/{folder}/orders/`
6. `ehr_integrations.requested_by` → `{ticket_id}`，`last_modified_by` → `Leo`
7. `order_clients.emr_name` null → `MDHQ`（**大寫**），`remote_folder_path` null → `/{folder}/orders/`
8. `sftp_folder_mapping`：先 SELECT 看 `/{folder}/orders/` 是否已存在，已在則不動

**操作建議**: 用 single Prisma `$transaction`，內部加 pre-check sanity guard（SELECT 比對當前狀態，不符就 throw），避免 STM 與 DB 真實狀態的時間差導致誤改。

---

## Optimantra RESULT_ONLY 標準範式

| 欄位 | 值 | 來源 |
|---|---|---|
| `ehr_vendor_id` | 9 | DB |
| `legacy_emr_service` | `OPTIMANTRA` | LTM |
| `sftp_result_path` | `/Prod/Input/` | vendor 共用，所有 Optimantra integration 一致 |
| `sftp_archive_path` | `""`（空字串） | Optimantra 慣例（不像 MDHQ 有 client-specific archive） |
| `sftp_ordering_path` | `null` | RESULT_ONLY |
| `report_option` | `PERSONALIZED` | Optimantra 預設（無 same-clinic 既有時） |
| `kit_delivery_option` | `NO_DELIVERY` | Optimantra 預設 |
| `ordering_enabled` / `result_enabled` | 0 / 1 | RESULT_ONLY |
| order_clients / sftp_folder_mapping | 不需要 | RESULT_ONLY |

`insert-ehr-integration.ts` 對 **非 MDHQ** vendor 的處理：
- `--folder` argument 不強制
- `sftp_result_path` 自動 lookup `WHERE ehr_vendor_id = X AND sftp_result_path IS NOT NULL` 既有 record（沿用 vendor 共用 path）
- `sftp_archive_path` 設空字串
- `sftp_ordering_path` 設 null
- 無 MDHQ 已知 bug（archive_path 缺尾 / 等）— 流程乾淨

## Optimantra FULL_INTEGRATION（Bidirectional）標準範式（VP-16193 + VP-16766 + 5 筆 LIVE 前例）

Optimantra = **vendor 共用固定 folder 模式**（與 MDHQ client-specific `/{folder}/...` 完全不同）。全 practice 共用 `/Prod/Input/`（results）+ `/Prod/Orders/`（orders）。

| 表 / 欄位 | 值 | 備註 |
|---|---|---|
| `ehr_integrations.integration_type` | `FULL_INTEGRATION` | Bidirectional |
| `ehr_integrations.sftp_result_path` | `/Prod/Input/` | vendor 共用 |
| `ehr_integrations.sftp_archive_path` | `""`（空字串） | Optimantra 慣例 |
| `ehr_integrations.sftp_ordering_path` | **`null`** | 即使 FULL 也 null；orders 走 order_clients.remote_folder_path + 共用 mapping |
| `ehr_integrations.report_option` | `PERSONALIZED` | 無 same-clinic follow 時 |
| `ehr_integrations.kit_delivery_option` | **`NON_BLOOD_ONLY`** | 對齊 kits_options=0；5/5 前例一致 |
| `ehr_integrations.ordering/result/sftp_enabled` | 1 / 1 / 1 | |
| `ehr_integrations.sftp_host:port` | 45.24.217.155:22 | vendor 9 |
| `order_clients.kits_options` | **0** | 對齊 NON_BLOOD_ONLY |
| `order_clients.emr_name` | `OPTIMANTRA`（大寫） | |
| `order_clients.remote_folder_path` | `/Prod/Orders/` | vendor 共用 |
| `order_clients.customer_name` | `Firstname Lastname`（**不含 suffix**） | Optimantra 前例慣例（如 "Jay Goodbinder"），與 Cerbo VP-16734 含 suffix 不同 |
| `sftp_folder_mapping` | **不新增** | 全 Optimantra 共用 1 列（id=67: /Prod/Orders/→/OPTIMANTRA/Prod/Order/, use_v2_pipeline=1）|
| `ehr_integration_status_history` | **不新增** | from-scratch new 不產生（只有 stub finalize PENDING→LIVE 才補）|

- **from-scratch new 是 Optimantra 常態**：不像 MDHQ「第一個 probe 找 PENDING stub」，Optimantra 多半無 stub、直接 INSERT（VP-16379 RESULT_ONLY、VP-16766 FULL 皆是）。Step 2 仍跑 probe 確認無 stub / 無 same-clinic 再執行。
- **insert-ehr-integration.ts 對 FULL_INTEGRATION 有 kit 錯配 bug**：line 292 寫死 `kit_delivery_option=NO_DELIVERY`，但 line 420 `kits_options=0`（兩者不對齊；NO_DELIVERY 應配 2）。用 script 須事後 UPDATE 修；**single Prisma `$transaction`（pre-check guard + INSERT×2 + in-tx verify + dry-run 預設）一次寫對，較適合 Optimantra FULL**。

---

## Follow That Patient（FTP）FULL_INTEGRATION 標準範式（VP-16720 + 24 LIVE 前例）

FOLLOWTHATPATIENT 跟 Optimantra 同屬 **vendor 共用固定 folder 模式**（非 MDHQ client-specific）。全 practice 共用 `/Prod/FollowThatPatient/Results/` + `/Prod/FollowThatPatient/Order/`。

| 表 / 欄位 | 值 | 備註 |
|---|---|---|
| `ehr_integrations.integration_type` | `FULL_INTEGRATION` | Bidirectional |
| `ehr_integrations.sftp_result_path` | `/Prod/FollowThatPatient/Results/` | vendor 共用 |
| `ehr_integrations.sftp_archive_path` | `""`（空字串） | |
| `ehr_integrations.sftp_ordering_path` | **`null`** | orders 走 order_clients.remote_folder_path |
| `ehr_integrations.report_option` | `CLASSIC` | FTP 前例一致 |
| `ehr_integrations.kit_delivery_option` | **`NO_DELIVERY`** | 對齊 kits_options=2 |
| `ehr_integrations.legacy_emr_service` | `FOLLOWTHATPATIENT` | |
| `order_clients.kits_options` | **2** | 對齊 NO_DELIVERY |
| `order_clients.emr_name` | `FOLLOWTHATPATIENT`（大寫） | |
| `order_clients.remote_folder_path` | `/Prod/FollowThatPatient/Order/` | |
| `sftp_folder_mapping` | **不新增** | 全 FTP 共用（id=251: /Prod/FollowThatPatient/Order/→/FOLLOWTHATPATIENT/Prod/Order/）|

### 「Expand to Bidirectional」ticket 模式（升級既有 RESULT_ONLY）

不是 from-scratch INSERT，主流程是 **mixed UPDATE + INSERT**：
- **UPDATE** 既有 RESULT_ONLY → FULL_INTEGRATION + `ordering_enabled=1`
- **INSERT** ticket 列出但 prod 沒既有的 missing pair（from-scratch FULL，contact 從 sibling row borrow）
- **INSERT** 所有相關 customer 的 `order_clients`（很可能既有 RESULT_ONLY 都漏 oc，順便補）

`insert-ehr-integration.ts` script 是 from-scratch INSERT 設計，**不適合 expand 流程**；用 single Prisma `$transaction` 才能 atomic 混合 UPDATE+INSERT。

---

## INSERT new (clinic, customer) pair — sibling borrow 要分兩種維度（VP-16720 教訓）

INSERT 一個新的 `ehr_integrations` row（譬如 ticket 列出但 prod 沒既有的 missing pair）時，要從**兩種 sibling** borrow 欄位：

| 維度 | Sibling 來源 | 該借的欄位 |
|---|---|---|
| **Clinic-level** | same-clinic 任一 LIVE row（同 vendor 同 clinic_id） | `clinic_name`, `clinic_address`, `clinic_city`, `clinic_state`, `clinic_zip`, `contact_name`, `contact_email`, `contact_phone`, `contact_title` |
| **Customer-level** | same-customer 任一 LIVE row（同 customer_id 跨 clinic）| `customer_npi`, `effective_npi`, `clinic_npi`（如果該 customer 在其他 clinic 已有 NPI 紀錄） |

**陷阱**：ticket 表常只列 customer_id + provider_name，不含 NPI。若按「only same-clinic borrow」會把 customer_npi 寫成 null，但同 customer 跨 clinic 的 NPI 應一致（customer 屬性）。事後要 UPDATE 補。

VP-16720 case：Anna Emanuel 43262 在 ticket 列 4 clinic（2930/8003/36290/144510）。144510 既有 RESULT_ONLY 已有 customer_npi=1073000691。3 個新建 (2930/8003/36290) borrow 時只取了 clinic-level 欄位，customer_npi 寫 null → 事後 UPDATE 補。

**正解 pseudocode**：
```ts
const clinicSibling = await findFirst({ clinic_id, ehr_vendor_id, status: 'LIVE' });
const customerSibling = await findFirst({ customer_id, status: 'LIVE' });
const payload = {
  ...clinicLevelFields(clinicSibling),
  customer_npi: customerSibling?.customer_npi ?? null,
  effective_npi: customerSibling?.effective_npi ?? customerSibling?.customer_npi ?? null,
  // ...
};
```

---

## `order_clients` 是 per-customer，不是 per (customer, clinic) pair（VP-16720 驗證）

**Rule**：批次處理跨 clinic 同 customer_id 的 provider 時，`order_clients` 只建 **1 row per customer**，跨 clinic 共用。

**Prod 慣例驗證**：「跨 2+ clinic 的同 customer_id provider」全部 oc 都是 1 row per customer（從 `ehr_integrations.customer_id` GROUP BY clinic_id 統計確認）。

**陷阱**：ticket 表常列「同 customer_id 在多 clinic」（如 Anna Emanuel 43262 跨 4 clinic）。若按 (clinic, cust) pair × 1 INSERT 會建出重複 oc rows。`order_clients` schema 沒 unique constraint on customer_id，DB 不會 throw。

**做法**：批次 INSERT order_clients 前先 dedupe `PAIRS` by customer_id 算實際 INSERT 計畫。VP-16720 失誤 case：建 24 oc 後手動刪 3 個重複。

**對照**：`ehr_integrations` 是 per (clinic, cust) pair（同 customer 跨 clinic 各一筆 row）；`order_clients` 是 per customer。兩張表的「主鍵維度」不同。

---

## Multi-Practice Provider

ticket 有表格列出 Practice ID / Provider ID 時：
- 每行 = 一筆 `ehr_integrations` record
- 解析全部行，不要漏

---

## Field Defaults（所有新 Integration）

| Field | Default | 備註 |
|-------|---------|------|
| `status` | `LIVE` | |
| `report_option` | `PERSONALIZED` | |
| `kit_delivery_option` | `NO_DELIVERY` | |
| `contact_name` | `Leo` | |
| `contact_email` | `hung.l@zymebalanz.com` | |
| `hl7_version` | `2.3` | |
| `sftp_enabled` | `1` | |
| `use_vendor_sftp_config` | `1` | |
| `requested_by` | **ticket_id**（如 VP-15955） | 不能留空 |
| `ehr_vendors.updated_by` | `Leo` | |
| `ehr_integrations.last_modified_by` | `Leo` | |

### Vendor-dependent fields（必須從 ehr_vendor 表查）
- `ehr_vendor_id` → `SELECT id FROM ehr_vendor WHERE name LIKE '%EMR_NAME%'`
- `sftp_host`, `sftp_port` → **從 ehr_vendor 表查，不能猜**
- `legacy_emr_service` → vendor code
- `api_enabled` → CHARMEHR(id=7) 為 1，其他為 0

### SFTP Path（所有路徑結尾必須有 `/`）
- `sftp_result_path` = `/{folder}/results/`
- `sftp_archive_path` = `/{folder}/results/archive/`
- `sftp_ordering_path` = `/{folder}/orders/`（不能遺漏）
- MDHQ 格式同上
- **共用 SFTP server**: `64.124.9.100`，不同 vendor 用不同 port（如 Breathermae=2222, FTP=2224, DocVilla=2225）
- 新 vendor 的 SFTP credentials 需先驗證連線，確認 port 和目錄結構

### 新 Vendor 上線流程
1. SFTP 連線驗證（確認 host, port, credentials, 目錄結構）
2. 新增 `ehr_vendors` 記錄（注意 `supported_hl7_versions` 為必填，JSON 格式如 `["2.3"]`）
3. 新增/更新 `ehr_integrations` 記錄
4. 如需 order_clients / sftp_folder_mapping 則一併處理

### Provider ID Missing 處理流程（ticket 沒給 provider ID）
1. **先重新拉 ticket description** — PM 可能後來在 description 補上（如 VP-16379 把 36899 補在 description 而非 comment）
2. **DB 反查 customer_name** — `SELECT customer_id, ... FROM order_clients WHERE customer_name LIKE '%firstname%lastname%'`，看是否能定位
3. **以上都沒有** → 在 Jira 留 comment 直接問 PM，不要自行推測 ID
4. 取得後一律 gRPC `GetCustomer(provider_id)` 驗證 name + NPI + clinic 對得上才執行 INSERT

---

## Vendor Name Mapping

| Ticket 上寫的 | DB Code（`emr_name` 填這個） | `ehr_vendors.code` |
|--------------|-------------------------------|---------------------|
| cerbo, mdhq | **MDHQ** | MDHQ |
| charm | CHARMEHR | **ChARM_EHR** |
| eclinical, ecw | ECW | ECW |
| athena | ATHENA | ATHENA |
| follow that patient | FOLLOWTHATPATIENT | FOLLOWTHATPATIENT |
| optimantra | OPTIMANTRA | OPTIMANTRA |
| docvilla | DOCVILLA | DOCVILLA |
| elation | — | ElationEMR |
| practice fusion | — | PF |
| power2practice | — | POWER2PRACTICE |
| praxis | — | PRAXISEMR |
| optimal dx | — | OptimalDX |
| health matters | — | HealthMatters |

- `order_clients.emr_name` 必須填 DB Code（第二欄），不是 ticket 名稱
- **case 一致性**: `order_clients.emr_name` 要用**上表 DB Code 的大小寫**（e.g. `MDHQ` 而非 `mdhq`）。`insert-ehr-integration.ts` 以 CLI `--emr-name` 原樣寫入，因此要傳 `MDHQ` 而不是 `mdhq`；若已寫成小寫，事後 `UPDATE order_clients SET emr_name = 'MDHQ' WHERE ...` 修正
- `ehr_vendors.code` 有 mixed case（legacy data），**不是全大寫** — 寫 SQL 時用實際值
- MySQL 預設 collation 是 case-insensitive，WHERE IN 匹配不受大小寫影響

---

## Vendor Public/Private 分類

`ehr_vendors.is_public` 欄位控制 Settings 頁面 dropdown 是否顯示（VP-16014 新增）

- **Source of truth**: Notion EMR Vendor List
- `is_public = true`（預設）: 新 vendor 自動公開
- `GET /ehr-vendors` API 預設只回傳 `is_public = true` 的 vendor
- Admin portal 的 vendor API **不受影響**（獨立 service method）

**Public vendors (18)**: APRIMA, ATHENA, CASCADES, ChARM_EHR, DOCVILLA, ECW, ElationEMR, EPRO, FOLLOWTHATPATIENT, GREENWAY, HARRIS, HF, MDHQ, MEDITAB, OPTIMANTRA, POWER2PRACTICE, PF, PRAXISEMR

**Private vendors**: BREATHERMAE, ELLKAY, GLO, HealthMatters, INSYNC, MARQIMEDICAL, MDHQTEST, NICHOLS, OptimalDX, THM, Unprescribed, VEJO, VEJOEcomm, VEJOPROGRAM, YHL, ZYMEBALANZ

---

## 必要 Tables

1. `ehr_integrations` — 主整合記錄
2. `order_clients` — 客戶資料
3. `sftp_folder_mapping` — **僅 ORDER mapping**

---

## 必用 Scripts（不要寫 raw SQL）

- `scripts/insert-ehr-integration.ts`
- `scripts/insert-order-client.ts`
- `scripts/get-customer-rpc.ts`
- `scripts/update-clinic-msh.ts`
- `scripts/check-db-state.ts`

---

## EMR Integration Removal

當 ticket 要求關閉/移除某 provider 的 EMR integration（如 vendor 那邊停用了 interface）：

**標準流程（status-based 停用，不要 DELETE 記錄本體）:**
1. `UPDATE ehr_integrations SET status='REJECTED', updated_at=NOW(), last_modified_by='Leo', requested_by='{ticket_id}' WHERE customer_id={X} AND clinic_id={Y}`
2. `INSERT INTO ehr_integration_status_history` 記錄 LIVE → REJECTED，`changed_by` 填 ticket number
3. `DELETE FROM order_clients WHERE customer_id={X} AND clinic_id={Y}`（FULL_INTEGRATION 才有）
4. `sftp_folder_mapping` **不需刪除**（無 LIVE integration 就不會被使用）

**為什麼用 REJECTED 而非 DELETE:**
- `result-generation.service.ts` 查詢是 `status='LIVE' AND result_enabled=true` — REJECTED 狀態自動跳過所有結果傳送
- 保留 audit trail，可逆
- 同效 DELETE，但安全

**Gotcha — Prisma `@updatedAt`:**
- `$executeRaw` / raw SQL **不會** 觸發 `@updatedAt`，必須手動 `SET updated_at=NOW()`
- `ehr_integration_status_history.changed_by` 必須填 ticket number（audit 需求）

---

## hl7_file_input Reprocess（已過 retry 上限的失敗）

當 ticket 要求重新處理已卡住的 hl7_file_input 記錄（如 provider 帳號晚於 integration 建立導致前批 order 失敗）：

```sql
UPDATE hl7_file_input SET retry_num = 3 WHERE id = {X};
```

- `retry_num` 從 0 改為 > 0 即可，cron 下次（15 分鐘內）會自動撿起
- customer/integration lookup 是 stateless 的，不需要清其他欄位
- 與「manual payment + order recovery」（HL7 triage）是兩個不同情境：reprocess 是「讓 cron 重試」，recovery 是「人工繞過 cron 補資料」
- **判斷該失敗單由 emr-v2 還是 Java cron 處理**（決定 reprocess 機制是否適用）：emr-v2 processor 遇 customer_not_found 會設 `parse_finished=true`（停止重試）；若 `parse_finished=0` + customer_not_found + `retry_num=0` → 是 **EMR-Backend Java cron** 處理（該 client 未在 emr-v2 cutover batch），`SET retry_num=3` 重撿適用（VP-16765 驗證）。emr-v2 的 `retry_num` 則是從 `INITIAL_RETRY_NUM=5` 倒數、SFTP 掃檔驅動，不靠 hl7_file_input 重掃。
- **`last_update_pod_name` 有同名歧義（HL7FAIL-20260722）**：on-prem cluster 的 deployment 與 AKS 同名（都叫 `lis-emr-v2-deployment-prod-*`），看 pod name 無法判斷該 row/檔案屬於哪個 cluster。要判斷 folder 的 owner 用 `sftp_folder_mapping.pipeline_location`（onprem/cloud），不要假設是 AKS。
- **原始 HL7 只存在 owning pod 的 local file**（`hl7_file_input.order_input` 常為 null；失敗的檔案不會 archive）：`retry_num` bump 讓 owning pod 從本機檔案重讀，是唯一的 re-place 途徑 — 沒有那個 pod 的檔案就無法手工重建訂單。所以 bump 前務必先把 integration 修好（先 INSERT/修正、再 bump，順序不可反）。

### hl7_file_input 欄位寬度限制（寫入前必 truncate）
| Column | Type | 易溢出來源 |
|--------|------|-----------|
| `emr_code_not_found` | `VARCHAR(255)` | OBR error_codes 累積、ClassCastException stack message |
| `customer_not_found` | `VARCHAR(45)` | `firstName + " " + lastName` 對長姓名超寬、payment fail reason |

EMR-Backend `ParseOrder.updateHL7FileInput` 只要任一欄超寬，UPDATE 就拋 `MysqlDataTruncation: Data too long for column` → bubble up to job-level PersistenceException → 中斷整個 cron run。寫入前一律 truncate（VP-15460 incident 修過）。

---

## HL7 Message Type Variants (ORM_O01 vs OML_O21)

EMR vendor 送來的 HL7 v2.5 order message type 不一定是 legacy 的 `ORM_O01` (General Order)。**Practice Fusion** 等 vendor 改用 `OML_O21` (Laboratory Order with detailed content)。

| Variant | MSH-9 | 共有 segments | 多出 segments |
|---------|-------|---------------|---------------|
| ORM_O01 | `ORM^O01[^ORM_O01]` | MSH, PID, ORC, OBR, IN1, GT1, OBX | — |
| OML_O21 | `OML^O21[^OML_O21]` | MSH, PID, ORC, OBR, IN1, GT1, OBX | SPM (specimen), SFT, UAC, ARV, PRT |

**EMR-Backend `HL7_package.parseOrderFromMessage` 只處理 ORM_O01**，OML_O21 會 ClassCastException。Quick fix：rewrite MSH-9 string 從 `OML^O21` 到 `ORM^O01^ORM_O01`，HAPI 用 ORM_O01 model parse、OML-only segments 在 non-strict mode 下 silently ignore（VP-15460 incident #159）。

**lis-emr-v2 worker 不踩雷**：`Hl7DecoderService` 是 segment-based（直接找 PID/ORC/OBR/OBX 名稱）不依賴 message type class — OML_O21 自動相容。

**判讀順序（HL7 file 卡單 triage 時）**：
1. `emr_code_not_found` 有值 → bundle / test code 找不到（既有 triage 流程）
2. `emr_code_not_found = "EXCEPTION: ClassCastException..."` → 看 message type，可能是 OML_O21 / 其他變種
3. 其他 exception → 看 EMR-Backend pod log

---

## Vendor File Size Limits

| Vendor | Limit | 建議閾值 |
|--------|-------|---------|
| Cerbo (MDHQ) | 15MB | 14MB |
| ECW | 20MB | 18MB |
| Epic | 25MB | 23MB |

---

## Auto-Integrate Origin Stub（PENDING stub 識別與 finalize 流程）

VP-16423 case 揭示一種 ehr_integrations PENDING record 來源：**internal staff 在 admin-portal 預建的 stub**（不是 provider 透過 Provider Portal 自助提交的真正 auto-integrate request）。

### 識別 PENDING stub 的 fingerprint
| 欄位 | 值 |
|---|---|
| `status` | `PENDING` |
| `integration_origin` | `NEW_INTEGRATION` |
| `ehr_vendor_application_id` | `null`（沒指到 vendor application）|
| `business_justification` / `business_model` / `service_provided` | 全空（`""`）|
| `assigned_to` | `null` |
| `requested_by` | 數字（user_id），不是 `VP-XXXXX` 票號 |
| `ehr_integration_status_history` | 1 筆 `null → PENDING`，`reason="Initial integration request submission"` |
| `sftp_*_path` / `msh06_receiving_facility` | 全 null |
| `kit_delivery_option` / `report_option` | schema default（`BOTH_BLOOD_AND_NON_BLOOD` / `CLASSIC` 等）|

業務情境：sales/TPM 預先在 admin-portal 替 practice 建 stub，等正式 integration ticket 進來時 finalize。

### Finalize 流程（ticket UPDATE PENDING → LIVE）
1. UPDATE ehr_integrations 補：sftp paths / msh06 / status=LIVE / ordering_enabled=1 / result_enabled=1 / sftp_enabled=1 / legacy_emr_service / requested_by=`VP-XXXXX` / last_modified_by=Leo / updated_at=NOW()
2. INSERT ehr_integration_status_history(`PENDING → LIVE`, changed_by=`VP-XXXXX`, reason=`finalize stub from <date> auto-integrate request`)
3. INSERT order_clients（stub 通常沒對應 order_clients，要手動補）
4. INSERT sftp_folder_mapping（同 stub 通常無對應，手動補）。**VP-16629 後新標準**（VP-16734 確認）：套 `ehr_vendor_sftp_templates`：`sftp_source_id=template.sftp_source_id`（Cerbo/MDHQ=3）、`local_folder=template.local_order_path`（`/MDHQ/Prod/Order/`）、`emrName=template.emr_name`（`MDHQ`）、`use_v2_pipeline=1`。**不再沿用** VP-16424 的 `sftp_source_id=NULL, use_v2_pipeline=0`（那是 hook 還沒導入前的舊寫法）
5. **不要** DELETE PENDING 記錄重新 INSERT — 會丟失原始 status_history audit trail
6. 保留 stub 預建的 `contact_name` / `contact_email`（admin-portal 填的真實 customer contact，不要覆寫成 Leo / hung.l@）

### Stub finalize 欄位選擇（VP-16423 / VP-16424 / VP-16617 / VP-16734 收斂）
**無 same-clinic LIVE follow target 時**：
- `report_option`: **通則 `PERSONALIZED`**（= Field Default / `getReportOption` fallback；Leo VP-16734 確認）。**CLASSIC 不是預設** — 過去 case 出現 CLASSIC 的原因是 (a) same-clinic follow 既有值剛好是 CLASSIC（VP-16423 17412 / VP-16245），或 (b) Leo 一次性指示採 stub schema default（VP-16424）。遇到 stub 原本是 CLASSIC 時跟 Leo 確認要不要覆寫（VP-16734：Leo 說「已是 CLASSIC 就不用特地改」→ 維持，但這是個案判斷不是規則）
- `kit_delivery_option=NO_DELIVERY`、`order_clients.kits_options=2`（**Leo 偏好**：VP-16424 + VP-16734 連續兩例確認。語意：both blood + non-blood 都由 clinic supplied，不寄 kit 給 patient）
  - **另一合法選項** `NON_BLOOD_ONLY/0`（non-blood ship to patient, blood by clinic）— ParseHL7.java:930-943 兩者都對齊；差別在 clinic 期待行為
  - **警示**：早期 LTM 曾錯誤寫 `NO_DELIVERY+kits=0`（兩者不對齊），VP-16617 audit 修正；現在的 `NO_DELIVERY/2` 是對齊正確版

**有 same-clinic LIVE follow target 時**：對齊既有 LIVE row 的值（filter `status='LIVE' AND business_justification != ''` 排除其他 stub）

**`kit_delivery_option` ↔ `kits_options` 對齊規則（不可違反）**：
- `NON_BLOOD_ONLY` ↔ `kits_options=0`（non-blood ship, blood supplied by clinic）
- `BOTH_BLOOD_AND_NON_BLOOD` ↔ `kits_options=1`（both ship）
- `NO_DELIVERY` ↔ `kits_options=2`（both supplied by clinic）
- 來源：`EMR-Backend/.../ParseHL7.java:930` switch case 是真 runtime authority；`ehr_integrations.kit_delivery_option` 是顯示欄位、必須跟 `order_clients.kits_options` 對齊、否則 audit / report 跟實際 Java 行為脫節

### Stub ≠ same-clinic 既有可 follow
判斷「same-clinic 既有」做 follow-existing rule（report_option / kit_delivery_option / old_clinic_id）時，必須 filter `status='LIVE' AND business_justification != ''`，否則會把 stub 的 schema default 當真實設定（VP-16423 踩過：把 stub 的 `kit_delivery_option=BOTH_BLOOD_AND_NON_BLOOD` 當 follow target，正確值是 `NO_DELIVERY` 對齊 kits_options=0）。

---

## Auto-Integrate（自助整合請求系統）

PRD: Confluence「Automated New EHR Integrations」(page 1781628967)

**目的:** 讓 provider 透過 Provider Portal > Settings > Third-Party Integrations 自助提交 EHR 整合請求，取代手動 ticket 流程。

**三大元件:**
1. Integration Request Form — provider 填表（supported vendor 或 "Not on the list"）
2. Integration Status Tracker — provider 查看請求狀態
3. Admin Review Dashboard — Unimod Panel 新 tab，Sales/TPM/PM 審核

**程式碼位置（lis-backend-emr-v2）:**
- Controller: `src/modules/integration-management/auto-integrate/controllers/integration-request.controller.ts`
- Service: `src/modules/integration-management/auto-integrate/services/integration-request.service.ts`
- Create DTO: `src/modules/integration-management/auto-integrate/dto/create-integration-request.dto.ts`
- API: `POST /integration-management/auto-integrate/requests`

**已存在的 PRD 表單欄位（DTO + DB）:**
- `businessModel` → `business_model` (VarChar 100)
- `businessJustification` → `business_justification` (Text)
- `serviceProvided` → `service_provided` (Text)
- `expectedVolumeRange` → `expected_volume_range` (Enum)
- `integrationType` → `integration_type` (含 OTHER option)
- `ehrVendorId` → `ehr_vendor_id` (Optional, null = 未選或 not on list)

**"Not on the list" 缺少的欄位（VP-14787）:**
- custom_vendor_name / company_name
- custom_ehr_name
- custom_ehr_website (URL)

**VP-14873（獨立 ticket）:** 將 unsupported vendor 請求分離到獨立 table + API

**`ehr_vendor_inquiry` 表（VP-14787/VP-14873 建、VP-16760 補完 internal review）:**
- 「Not on the list」unsupported vendor 請求的**獨立表**（≠ ehr_integrations）。模組同 auto-integrate；files `vendor-inquiry.controller.ts` / `vendor-inquiry.service.ts` / `(create|update|approve|reject)-vendor-inquiry.dto.ts`
- `status`: `PENDING_REVIEW → APPROVED | REJECTED`（enum `VendorInquiryStatus`）。**純需求追蹤：approve 不建 EhrVendor/EhrIntegration、不寄信。**
- Endpoints（base `/integration-management/auto-integrate/vendor-inquiries`）：`POST /`（customer submit）、`GET /?status=`(review queue)、`GET /:id`、`POST /:id/approve`、`POST /:id/reject`(rejectionReason 必填)、`PUT /:id`、`GET /:id/history`
- **internal gate**：approve/reject/history + list「跨 customer 看全部」皆需 `internal_user_role`（Sales 也算 internal，非 admin）；一般 customer 只看自己。要新增 internal 動作時，list 的可見性 gate 要一起放寬，否則能動手卻看不到佇列。
- **AC「Every resolution action writes an audit log entry」→ `ehr_vendor_inquiry_status_history`**（append-only，mirror `EhrIntegrationStatusHistory`：inquiry_id FK / from_status / to_status / reason / changed_by / created_at），每次 approve/reject 與 status update 同一個 `$transaction` 寫一筆。inline `reviewed_by`/`reviewed_at`/`rejection_reason` 只存最新狀態、會被覆蓋，**不能當 audit trail**。此 pattern 通用於本 repo 任何 approve/reject ticket。

---

## 插入後驗證 Checklist

### ehr_integrations
customer_id, clinic_name, clinic_id, msh06, sftp_host, sftp_port, sftp_result_path, sftp_archive_path, sftp_ordering_path, requested_by, status, ehr_vendor_id, legacy_emr_service, **report_option（same-clinic follow）**, **kit_delivery_option（same-clinic follow）**

### order_clients
customer_name（gRPC）, customer_id, customer_provider_NPI, customer_practice_name, clinic_id, emr_name（**DB Code 原始大小寫**，如 `MDHQ` 非 `mdhq`）, remote_folder_path, **old_clinic_id（same-clinic follow）**

### sftp_folder_mapping
server_folder, local_folder, emrName

---

## hl7_file_input Triage（Regular Ops）

定期檢查 EMR order 處理失敗的記錄並手動復原。

### 查詢失敗記錄
```sql
-- Azure MySQL: lisportalprod2.mysql.database.azure.com / lis_emr
SELECT id, file_name, emr_code_not_found, sftpDir, emr_service,
       retry_num, parse_finished, received_time
FROM hl7_file_input
WHERE parse_finished = 0 AND retry_num = 0
  AND received_time >= NOW() - INTERVAL 72 HOUR
ORDER BY received_time DESC;
```

### 失敗分類與處理

| 特徵 | 原因 | 處理方式 |
|------|------|---------|
| `emr_code_not_found` 有值 | Test code / bundle mapping 找不到 | 報 PM（Kristine），由 Order team 建立 bundle |
| `order_input` 有值, `sample_id=NULL`, `emr_code_not_found=NULL` | 下單流程失敗（payment 或 Order API） | 手動 payment + order recovery |
| `order_input=NULL`, `emr_code_not_found=NULL` | HL7 parsing exception | 查 EMR-Backend pod logs |

### 取得 provider NPI / 原始 HL7 / DB 存取（2026-06-29 補）
- **`hl7_file_input.order_input` 不是原始 HL7**，是 emr-v2 轉換後的**送單 payload(JSON)**（含 `orderItems`/`item_id`/`chargeMethod`/`emr_payment_fail_reason`/`clinic_id`）；customer 解析失敗時為 NULL。→ 要拿 **provider NPI（ORC.12 / OBR.16，NPI 是第一個 `^` 子值）必須讀原始 `.hl7` 檔**，DB 沒存。
- 原始 HL7 路徑：持久 `/EMR_storage/HL7Message_prod/<emr_service>/Prod/Order/<file_name>`（讀得到）；ephemeral `/tmp/hl7/<...>`（pod 重啟即清掉，舊單讀不到）。`localDir` 欄位指向其一。
- **存取只能走 pod 內**：emr-v2 prod DB 的 grant 綁 pod IP，從 appserver04 直連 `mysql` 會 `Access denied for 'lis_emr'@<appserver04 IP>`。→ 用 **pod 內 node prisma 查 DB + `fs.readFileSync` 讀 raw HL7**（`kubectl exec <prod-pod> -c lis-emr-v2-prod -- sh -c 'echo <b64> | base64 -d | node'`）。
- **customer_not_found="<First Last>"** = 該 ORC.12 NPI 在 `ehr_integrations` **0 筆**（provider 未 onboard）→ 要建 LIVE+ordering integration 才解析得到。**區別** `emr_code_not_found`：customer 已解析成功，是 battery/bundle code（如 `discountpanel{n}`→官方 bundle map）在該 customer 找不到。
- **appserver04 SSH 連太多次會被 fail2ban 擋**（接受密碼但指令零輸出）→ 用 `ssh -o ControlMaster=auto -o ControlPath=/tmp/cm.sock -o ControlPersist=15m`（[[reference_appserver04_ssh]]）建一條 master，後續所有查詢重用同 socket、免密碼免重連。

**Raw HL7 archive 全貌（VP-17286 全量 audit 2026-07-15 驗證）：**
- **On-prem node 直讀**：`ssh leo@192.168.60.5`（appserver04），檔案在 `/mnt/storage/EMR_storage/HL7Message_prod`——DB 存的 `/EMR_storage/...` 是同一個 PV，node 端 mount prefix 是 `/mnt/storage`。批量 audit 比 pod 內逐檔讀快得多。
- **Archive 佈局 per vendor 不同**：多數 vendor 是 `<VENDOR>/Prod/Order(Archive)/`；**MDHQ 是 per-clinic `<clinic>_InputArchive/`**（沒有單一 OrderArchive）→ 用 DB path 對不上時，改建**全 tree filename index** 再 match（2026 audit：25,716 檔案 index、1884/1898 命中）。
- **SFTP 端回溯性**：只有 Vibrant 共用 host `45.24.217.155` 留 OrderArchive（THM 等可回抓）；**MDHQ host `34.199.194.51` fetch 後即清空**（clinic /orders 目錄空、無 archive）→ MDHQ raw 只能靠 on-prem PV。`localDir=/tmp/hl7/...` 的 rows 是 pod ephemeral、沒進 archive tree，永久拿不回。
- **PID-7/8（DOB/sex）在這些 vendor 的 feed 實務上必填**：1884 個 2026 raw 檔 0 缺（每 vendor 都 0）+ 1527 patient record 交叉驗證 0 缺 → eligibility 的 IncompletePatientInfo rule 不會因 gender/DOB 擋 HL7 路徑訂單（address 未 audit）。

### OBR Prefix → Order Service API Mapping（**先看 prefix 再選 API，不要混用**）

`EMR-Backend/.../ParseHL7.java` 對不同 prefix 走完全不同 path，誤判 API 等於白查：

| OBR prefix | ParseHL7 line | In-memory map | Order Service API |
|---|---|---|---|
| `discountpanel{n}` | 444 | `officialBundleIdToBundleMap` | bundle mapping |
| `VAREQUISTION*` (含 `VARequisition`) | 457 ("requ") | `emrCodeToPackagePriceMap`（key 是 lowercase EMR code）| **`packagePriceMapping`** |
| `VATEST*` | 487 ("test") | `testOrderTypeIdToPackagePriceMap`（key 是 numeric test id）| `packagePriceMapping` |
| `VACP{panelId}` | 516 | `customOldOrderTypeIdCustomerIdToBundleMap` → `customOldOrderTypeIdClinicIdToBundleMap` | `getLegacyBundleMapping` |

**VAREQUISTION 流程細節:**
- 先過 ParseHL7 line 462 的 oldGroupID → newGroupID rename（240/241/242/252/277/271/288 → 332/326/327/330/331/260/302）
- 然後 `OrderTestClient.emrCodeToPackagePriceMap.get(obrBatteryID.toLowerCase())`
- API: `GET https://api.vibrant-wellness.com/v1/portal/order/staging/mapping/packagePriceMapping`（per `OrderEnvConfig.PACKAGE_PRICE_MAPPING`）
- 找不到或 `isOrderable != "true"` → `errorCodes.add(obrBatteryID)`

**VACP 流程細節:**
- VACP 後面的數字當 `panelId`（VACP38902 → 38902）
- Lookup 順序: `panelId,customerId` → `panelId,clinicId` → 都找不到就 errorCodes
- API: `GET api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd`
- Response 是 dict（key=bundleId），搜尋 `oldOrderTypeId` 匹配 panelId

**Anti-pattern:** 看到 `emr_code_not_found` 就直接查 bundle mapping。先看 prefix；VAREQUISTION 走 `packagePriceMapping` whitelist，跟 VACP custom bundle 完全是兩回事。

**EMR shortcut auto-sync 架構結論 (2026-06-17 huddle 討論，未定案):** 把可下的 shortcut code 清單同步給 EMR（讓 provider 在 EMR 端選）**不該由 emr-v2 蓋新 endpoint**。理由：(1) **非一次性** — catalog 動態，emr-v2 自己每 30 分鐘 `@Cron` re-pull (`order-mapping-cache.service.ts:50`)，custom bundle 有 `expireTime` 會到期；(2) **資料/控管權在上游** — VAREQUISTION 來自 pricing `getLegacyPackagePriceMapping`、VACP 來自 `getLegacyBundleMapping`，custom bundle 由上游 pricing/ops 建，emr-v2 只是下游消費者。→ 正解是接**上游 / 既有 portal 的 per-customer orderable catalog API**（portal 本來就在顯示給人下單，很可能已有）。emr-v2 唯一獨有的是 **code 格式規則**（package.uniqueemrcode→VAREQUISTION；bundle.oldOrderTypeId+customer_id→VACP），頂多提供格式規則，不該當 catalog publisher。詳見 auto-memory `project_emr_shortcut_sync`。

### 手動 Payment + Order Recovery

**前置:** 從 `sftpDir` 反查 clinic/customer:
```
sftpDir → order_clients.remote_folder_path → customer_id → ehr_integrations.clinic_id
```

**Step 1: 取得 payment method**
```
GET vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods
  ?customer_id=X&clinic_id=Y
Header: Authorization: {JWT with role="clinic", getTokenCustomerPM=true}   ← 不加 "Bearer " 前綴！
```
Response: `{clinic_payment_methods: [...], customer_payment_methods: [...]}`，每筆有 `payment_token`/`customer_token`。

**Step 2: transactionPay 扣款**
```
POST vibrant-america.com/lisapi/v1/charging/transaction/pay
Header: Authorization: {JWT with role="clinic"}   ← 不加 "Bearer " 前綴！
Body: {
  account_id, account_type: "customer", amount, type: "card",
  currency: "usd", charge_type: "testorder", token_platform: "stax",
  payment_source: "emr", payment_token, customer_token, new_sample: true
}
→ 回傳: sample_id, payment_transaction_id, julien_barcode
```
**⚠️ 這兩個 API 若少了 query params 或誤加 "Bearer " 前綴，會回 `400 invalid customer_id`（VP triage 2026-07-01 撞到，run_triage.py 修正）**。Step 3 缺 `lisCookie` header 則下單會直接失敗（同次事故撞到）——**扣款一旦成功即不可逆**，若下單緊接失敗會造成「已扣款、無訂單」中間態，須人工補下單或退款，不能讓 daily job 對同一筆記錄重跑（會重複扣款）。

**Step 3: Order API 下單**
```
POST vibrant-america.com/lisapi/v1/portal/order/orderTest/order
Header: Authorization: Bearer {JWT with role="customer"}, lisCookie: ""
Body: order_input（更新 sampleId, payment_id, julienBarcode 為 Step 2 結果）
→ 回傳: testOrderId, sampleId
```

**Step 4: 更新 DB**
```sql
UPDATE hl7_file_input SET
  parse_finished = 1, sample_id = {new}, payment_id = {new},
  julien_barcode = {new}, sample_id_payment = {new}, retry_num = 0
WHERE id = {X};
```

### JWT Token Generation
```python
# prod secret: 從 EMR-Backend/src/main/resources/dependencies/orderApi.yaml 的 jwtSecret.prod
payload = {
    "userId": 54674, "user_permission": "3f903fe0002",
    "customer_id": X, "clinic_id": Y, "old_clinic_id": X,
    "internal_user_id": 786, "internal_user_name": "bolin.l",
    "internal_user_role": "admin",
    "role": "clinic" or "customer",  # payment=clinic, order=customer
    "getTokenCustomerPM": True,      # payment only
    ...
}
# sign with HS256
```

### EMR-Backend Order Processing 流程 (ParseOrder.java)
1. Cron SELECT: `retry_num > 0 AND parse_finished = false`
2. HL7 parsing: `HL7_package.parseOrderFromMessage()` → OBR test codes 查 bundle mapping
3. Payment: `ChargeClient.getAllPaymentMethods()` → `ChargeClient.transactionPay()`
4. Generate sample ID: `GrpcService.SAMPLE.GENERATE_SAMPLE_ID`（如果 payment 沒產生）
5. Order: `OrderTestClient.sendOrder()` → POST Order API
6. 成功: `parse_finished=true`, `sample_id` 設定
7. 失敗: `retry_num--`, 維持 `parse_finished=false`
8. `INITIAL_RETRY_NUMBER = 5`，耗盡後永久卡住

### SFTP Credentials（EMR-Backend 用）
- MDHQ (Cerbo): `ehr_vendors` id=1, host=34.199.194.51, port=2210, user=vibrantamerica
- THM: `emr_sftp_source` id=19, host=45.24.217.155, port=22, user=THM
- PF (Practice Fusion): host=45.24.217.150, port=2222, user=pf_sftp

### `ehr_vendor_sftp_templates` — vendor SFTP / emr_name single source of truth (VP-16629)

新表（2026-05-19 加），lis-backend-emr-v2 內 per-vendor 預設 SFTP path / emr_name / local-mount，create flow + Cerbo approve hook 都從這查。

**Schema** (`prisma/schema.prisma:974`):
| col | 用途 |
|---|---|
| ehr_vendor_id (UNIQUE) | FK to ehr_vendors |
| emr_name | 寫入 `ehr_integrations.legacy_emr_service`。Cerbo 一律標準化為 `'MDHQ'` |
| sftp_source_id | FK target for `sftp_folder_mapping.sftp_source_id` upsert |
| sftp_order_path | Cerbo: `'/{folder}/orders/'`；其他 vendor: 具體 path |
| local_order_path | e.g. `'/MDHQ/Prod/Order/'` |
| sftp_result_path | Cerbo: `'/{folder}/results/'`；其他: 具體 path |
| local_result_path | （現在多數 NULL） |

**Create flow（`IntegrationRequestService.create()`）derive 邏輯**:
- Lookup template by `ehr_vendor_id`，沒 template → `400 BadRequest`
- Cerbo（`vendor.code/name.toUpperCase()` 含 `MDHQ` 或 `CERBO`）必須帶 `technicalRequirements.folder`，substitute `{folder}` → 寫 `sftp_ordering_path` / `sftp_result_path`
- 非 Cerbo: paths 抄 template verbatim
- `legacy_emr_service = template.emr_name`
- `reportOption: 1 | 2` → `CLASSIC` / `PERSONALIZED`

**Cerbo approve post-hook (`StatusManagementService.ensureCerboOrderFolderMapping`)**:
- approve 成功後，若是 Cerbo + `sftp_folder_mapping.server_folder = integration.sftp_ordering_path` 不存在，insert：
  - `server_folder = integration.sftp_ordering_path` (e.g. `/asquaredemr/orders/`)
  - `local_folder = template.local_order_path` (`/MDHQ/Prod/Order/`)
  - `emrName = template.emr_name` (`'MDHQ'`)
  - `sftp_source_id = template.sftp_source_id`
  - `use_v2_pipeline = true`
- Fire-and-forget try/catch（approve 主動作已 commit，post-hook 失敗 log 不中斷）

**Seed pattern**:
- script `scripts/seed-ehr-vendor-sftp-templates.ts`（gitignored），從現有 `ehr_integrations` 抓 latest per vendor + `sftp_folder_mapping` 對 emrName multi-candidate match（含 underscore stripping + case insensitive collation）
- 部分 vendor 在 sftp_folder_mapping 沒 order row（POWER2PRACTICE / OptimalDX / GREENWAY / HARRIS / Cascades / EPRO / Marqimedical / DocVilla）— Leo 確認不需要 order path
- Manual UPDATE 補的：ATHENA / HF / GLO / HealthMatters / PraxisEMR / Unprescribed / NICHOLS / VEJOProgram
- Rupa Health 在 sftp_folder_mapping 有 1 row 但 `ehr_vendors` 表沒這 vendor，FK 限制下不能加 template — 略過

**Cerbo SFTP path convention**: `/{clinicFolder}/orders/` 跟 `/{clinicFolder}/results/`，每 clinic 一份 folder。`clinicFolder` 由 PM 在 create request 帶 `technicalRequirements.folder` 指定（regex `^[a-zA-Z0-9_-]+$`，1-100 chars）。

**MySQL `utf8mb4_unicode_ci` collation 是 case-insensitive**：Prisma `where: { emrName: 'APRIMA' }` 自動 match 'Aprima'，不必 LOWER。但 underscore 差異（'ChARM_EHR' vs 'CHARMEHR'）要 multi-candidate（試 `vendor.code`, `vendor.name`, `replace(/_/g, '')` 版本）

### Integration request approve/reject endpoints (VP-16629)

- `POST /integration-management/auto-integrate/requests/:id/approve`
- `POST /integration-management/auto-integrate/requests/:id/reject`
- Thin wrapper delegate 到 `StatusManagementService` 既有 `updateStatus` (transition + audit + email)
- Auth: `JwtAuthGuard` + `user.internal_user_role` 必填
- Reject `reason` 必填 (1-500 chars)，寫到 `EhrIntegrationStatusHistory.reason`，觸發既有 `sendRequestUpdateEmail`
- Approve `reason` optional（預設 `'Integration request approved'`）
- 既有 `PUT /:id/status` (generic transition) 保留不動
- Audit 全寫到既有 `EhrIntegrationStatusHistory` 表，**不動 ehr_integrations 主表 schema**

### gRPC cloud-mirror fallback pattern (VP-16685 + INCIDENT-2604156666 lesson)

**規則 — 「Cloud version」必須同 package、同 port、同 backend language 才能當 fallback primary**

- **Host migration (安全)**：cloud mirror @ 同 port、同 proto package、同 backend code。例：
  - `10.224.0.199:30276` 鏡像 `192.168.60.6:30276` (`lis` package, Java) — VP-16685 wrap (`tryCloudThenOnPrem`)
  - `10.224.0.199:30600` 鏡像 `192.168.60.6:30600` (`testresult` package) — INCIDENT-20260518 既有 fallback
  - Wrap 設計：`primary cloud → on transient error fallback on-prem`，business error 直接 throw。helper：`grpc-client.service.ts` 的 `tryCloudThenOnPrem` (EMR) / `with-cloud-fallback.util.ts` (Calendar)
- **Service migration (要當全新 integration 處理)**：換 port / 換 package / 換 backend language — 是平行 service 不是 upgrade。例：
  - v1 `lis` (`:30276`, Java) vs v2 `coresamples_service` (`:32100`, Go) 是 **平行兩個 service**，不是 v1→v2 upgrade
  - 各 caller 設計用途不同；不要看到 v2 就以為該全切過去

**Go gRPC 序列化坑（INCIDENT-2604156666 根因）**：

- Go `time.Time{}` zero value → JSON `"0001-01-01T00:00:00Z"`（不是 null / empty）
- Go `int64(0)` → `"0"`、Go `string("")` → `""`
- Java/Node 對 missing field 通常回 null/undefined
- 對 missing/不存在的 timestamp，Go server 不會留空 — 會送出 year=0001。如果 client 用 `if (field)` 偵測 missing 永遠看到「有值」
- 影響範例：2026-05-19 起 c0852d0 切 v2 primary 後，14 vendor / 990 個 result HL7 OBR-7+OBR-14 = `00010101000000` push 到 vendor SFTP

**切換 RPC primary / 替換 backend service 前 checklist**：

1. 看 git blame 確認原作者意圖 — 是否真的 designed as 替換還是 parallel
2. 跑 read-only diff script：對 N 個 representative sample 打新舊兩邊、`JSON.stringify` 比對；邊界 case (missing/null/過去未來日期/空字串) 都要 cover
3. 不要因為「proto 一樣」就 skip — 同 proto 不等於同 marshalling（string/optional/nil/zero 跨 language 全不同）
4. 切換後第一個工作日 grep production HL7 / DB content 抽幾筆人工檢查
5. 詳見 user-level memory `feedback_end_to_end_equivalence.md`

### order_clients ↔ ehr_integrations sync semantics（INCIDENT-20260529 cleanup）
`order_clients` 是 V1 EMR-Backend Java 的 NPI → customer 路由表。**如果一個 (customer, clinic, NPI) 出現在 `order_clients` = V1 確實在處理它的訂單 = ei 該標 `integration_type=FULL_INTEGRATION` + `ordering_enabled=1`。**

**Drift 是常態**：5/29 sync 時發現 LIVE ehr_integrations 1022 row 裡 **826 row 是 `RESULT_ONLY+1`**（合約 RESULT_ONLY 但實際 `ordering_enabled=1`，被 v1 routing）+ **80 row 是 `RESULT_ONLY+0` 但在 order_clients**（真正下單但 ei flag 兩欄全錯）。v1 truth 跟 v2 metadata 漂移很容易發生，因為 enrollment / migration script 沒強制 sync。

**Sync UPDATE 寫法（match 邏輯）** — 三種 key 都要 OR、避免 NULL 漏網：
```sql
JOIN order_clients oc ON
     (oc.customer_id = ei.customer_id AND oc.clinic_id = ei.clinic_id)
  OR (oc.customer_provider_NPI = ei.customer_npi COLLATE utf8mb4_unicode_ci
      AND oc.customer_provider_NPI <> '')
WHERE (ei.integration_type <> 'FULL_INTEGRATION' OR ei.ordering_enabled = 0)
```
**仍會漏一種 case：cust_id 配上但 clinic_id 不同 + NPI 兩邊都 NULL**（V1 用 clinic_id=customer_id placeholder pattern，V2 已升級成真實 clinic_id）。修法：第二輪反向 audit 用 `EXISTS oc WHERE oc.customer_id = ei.customer_id` 抓漏。詳見 `patterns.md` 「UPDATE-WHERE-JOIN scope 必反向 audit」。

**Collation 必加**：`order_clients` (utf8mb4_0900_ai_ci) vs `ehr_integrations` (utf8mb4_unicode_ci) 不同 → NPI 字串比對要 `COLLATE utf8mb4_unicode_ci`。

**整套 sync UPDATE 後 audit 三件事**：
1. ROW_COUNT 對得上預期
2. Re-fetch 同樣 ID list 後逐 row diff 確認全部 FULL+1（per [[feedback_batch_db_verify]]）
3. 反向 broader-criterion 找漏網（per `patterns.md`）

**Cat 1 (oc orphan)**：225 個 oc customer 完全沒 ei row — v1 routing 有但 v2 ei 還沒建檔。不能 UPDATE 解決，要 INSERT 新 row（default 值 status / go_live_date / clinic_name / contact / sftp_paths 等需 PM 決定）。系統性 migration debt，5/29 沒動。

### `integration_type` vs `ordering_enabled` / `result_enabled` 語意
- `integration_type` (enum: ORDER_ONLY / RESULT_ONLY / FULL_INTEGRATION / OTHER) = **合約/分類**標籤、人填的
- `ordering_enabled` / `result_enabled` (tinyint) = **runtime gate**、實際決定 v1/v2 是否處理 order / result
- 客戶詢問「is this clinic placing orders from EMR」**看 `ordering_enabled=1`**，不是 `integration_type`。`RESULT_ONLY + ordering_enabled=1` 是正常 LIVE 狀態（合約叫 result-only 但實際雙向）

## Result pipeline go-live 時序缺口 — report_finished 早於 integration 上線會被靜默丟棄（journal 2026-07-02）

- 事實鏈（accession 2606116259/2606116226, customer 51154）：report_finished kafka event 到達時 `findEligibleResultIntegrations` 回空 → `kafka-report-finished-listener.service.ts:268` 直接 return，offset 照 commit → event 永久消失。該 integration 的 `created_at` 比 event 晚 ~11.5h（一建立就 LIVE）。
- 三個設計缺口（截至 2026-07-05 未修，只回報）：
  1. 查無 eligible integration = 靜默丟棄，只有 `logger.debug`（prod 看不到），`result_transmission_records` 0 rows、無任何 DB 痕跡。
  2. integration 轉 LIVE / 開 `result_enabled` 時**沒有 backfill** 上線前已 finished 的 report。與 VP-16968「開 flag 只對未來生效」同族，方向相反（這次是 flag 晚開）。
  3. `handleMessage` catch-all 吞錯後 offset 一樣 commit → transient DB error 也永久丟 event。
- 診斷特徵：`result_transmission_records` 該 sample **0 rows** = event 根本沒進 pipeline（pipeline 失敗一定留 row + BullMQ retry；SFTP hang 會留 GENERATING/ERROR）。
- 補救：`result.service.ts#generateResultHl7(sample_id)` 手動觸發補發。
- Debug 手法：repo 本地 `.env` 的 `DATABASE_URL` + `node_modules/mysql2` 直查 prod（read-only），不需 mysql client / pod exec。

## emr-v2 GenerateSampleID 從未生效 + order replay 安全準則（VP-17120 / VP-17318, 2026-07-02）

- **GenerateSampleID 自 VP-16463 port 起就沒 work 過**：proto 欄位是 `sampleId`（camelCase）但 client 帶 `keepCase:true` 讀 `response.sample_id` → undefined → `parseInt(x || '0')` 靜默變 0。5/28 前的非零 patientPayLater id 全是 Java EMR-Backend 寫的。
- `sendOrder`（POST /v1/portal/order/orderTest/order）收到 sampleId=0 會**自行分配正確 id**（70/74 zero-id orders 成功）；卡住的是該路徑上偶發的 sendOrder 失敗。
- **coresamples v2 GenerateSampleID sequence 落後 ~311k**（live probe 回的 id 全是既有 sample）→ 只修欄位名會注入撞號 id；order path 在 coresamples 修好 sequence 前**不得**使用此 RPC。Fix branch `bugfix/leo/VP-17318`：finalizer 直接送 0、client 讀正確欄位並 reject invalid、[RETRY-EXHAUSTED] loud log。
- **replay 安全準則**（非冪等 POST：client-failure ≠ server-failure）：
  - replay 前先查 `lis_core_v7.sample` 該 patient 有無 sample — 「失敗」的 attempt 可能已在 server 端建單（6517/18/20 就是）。
  - 手動 backfill `hl7_file_input.sample_id` 時**必須同時補 `emr_sample` row**，否則 result 回來 matching 會斷。
  - control_id/emr_order_id 來源依 vendor 而異：OPTIMANTRA = 檔名數字；MDHQ = 檔案內容的 MQ* id（檔案丟失即無法重建，向 vendor 要 MSH.10，**不要**請 vendor resend — 會重複下單）。
  - THM 在自家 SFTP 有 `/Prod/OrderArchive` 可撈回原檔；OPTIMANTRA/MDHQ 無。
- Retry 雙倍燒毀陷阱：AKS 測試 pod 與 on-prem pod 同時跑 fetch + retry-rescan，redlock 各自鎖在自己的 redis sidecar → 無跨 pod 互斥；沒檔案的 pod 用「Local file missing」燒 retry_num、有檔案的 pod 用真失敗燒 → retry 兩倍速耗盡。Phase B cutover 前 retry-rescan 也要 gate 在 intake role。

## Result push levels — per-report / per-sample-type partial push（VP-17344, 2026-07-08，dormant 上線）

- **機制**：`ehr_integrations.result_push_level` ENUM('WHOLE_ORDER','PER_REPORT','PER_SAMPLE_TYPE') DEFAULT WHOLE_ORDER + `result_transmission_records.push_scope_key`（如 `SAMPLE_TYPE:EDTA` / `REPORT:VA`；whole-order 記錄 = NULL，新舊互不干擾）。全 fleet 部署時 100% WHOLE_ORDER（零行為變化）；啟用 = `UPDATE ehr_integrations SET result_push_level=... WHERE id=...`，60s listener cache 內生效，rollback = 改回 WHOLE_ORDER。
- **設計定數**：~~partial push 強制 `add_report='0'`~~ **2026-07-25 起（VP-17493, PR #288/#289 prod live）PER_SAMPLE_TYPE partial 會帶 PDF**：listener 對 SAMPLE_TYPE scope 傳 `add_report_override=undefined` → 從 `report_option` 解析（CLASSIC→'1'）；PDF 下載失敗 = 單次嘗試（maxRetries 0，避免 backoff spiral）→ WARN + degrade 成 data-only，job 不失敗、無 placeholder。PDF 是 cumulative snapshot（同 sample 後續 scope 的 PDF 會變大）。**PER_REPORT 仍固定 '0'**（data-only，scope 決策）。whole-order path 未動 — 它仍有 placeholder-PDF fallback 債（下載全敗時送 junk PDF），已開 **VP-17503** 追蹤；partial-level integration 仍保留 final whole-order push（no-stall AC）；redraw 一律 whole-order；REPORT scope 已 TRANSMITTED 永不重推、未送達只擋 24h；SAMPLE_TYPE scope 24h 後可重推（redraw→re-finish）。gate 查詢失敗 = fail-CLOSED（空集合、不留 stale cache，partial 暫停、whole-order 不受影響）。
- **記錄定位**：partial job 帶 `transmission_record_id`，processor 的 retry/failure 更新精準打該 row——不能用 scope filter updateMany（會改寫較舊的 TRANSMITTED sibling）。已知 latent：whole-order updateMany 仍會打 >24h 舊 sibling（pre-existing，未動）。
- **Ops doc**：Confluence「Result Granularity」folder（pages/2542501892）。測試 integrations `cvp17344e2etest0000000001/2`（customer 999997 → Vibrant 自家 SFTP /Test/Input/EMR_V2/VP17344*）。

### general_sample_events 事件語意（設計 partial push 時查證，ClickHouse 192.168.62.85:8123 kafka db）

- **`sample_type_all_finish`**（lis-result，2026-07-08 Yekai 新增）：某 tube/sample type 全部 tests finished 即發、不管 TNP；是 `sample_type_all_finish_with_tnp` 的 superset（後者仍在 TNP≥1 時另發，獨立訊息、既有 consumer 不受影響）。~4-5k/day。
- **`new_report_status_updated`**（lis-report）：每次 per-report status 變化都發（**ready 和 viewed 都算**），consumer 要自己 diff 哪些 report 新 ready；producer 送 **sample_id=0**，要用 `getSampleIdByBarcode(accession)` 反查。~1.3k/day partial。
- **`personalized_report_ready`** = barcode 下**全部** reports 完成才發，不是 per-report——per-report trigger 別用它。
- **lis-result 系事件 customer_id NULL / clinic_id 0** → 必須 `grpcClient.getSampleRelevantInfo(sample_id)` 解析 customer/clinics（回全部 clinicIds，eligibility 查詢要 `clinic_id IN (...)` 不能只拿第一個）。
- `products_finished`：per-product finish，~0.9% 會重發 2-6 次 → consumer 需冪等。
- 順序：`results_all_finished` → `sample_finished`(/`_with_tnp`) → `report_finished`（最後，report 生成完）。
- **跨團隊 event gap 會在 ticket 進行中消失**：前一天查證「沒有 plain per-sample-type finish event」，回報後 producer 團隊一天內加了 `sample_type_all_finish`——設計 workaround 前先重驗 ClickHouse ground truth。

## API order path (VP-17283/VP-17286) — staging E2E 測試身分與代碼（2026-07-13 建立）

- **Endpoint（staging）**：`https://api.vibrant-america.com/v1/lis/emr-service-staging/order-intake` — AKS ingress 走這個 path，**沒有 `/api/v1` prefix**。JWT 用 dev secret（PyJWT 自簽），身分 customer 999997 / clinic 10136。staging pod `env=dev` → order-staging 上游；`ORDER_INTAKE_MODE` 在 cluster ConfigMap `lis-emr-v2-config`。
- **測試病人**（customer 999997 底下，searchPatient API 可查）：`477769` TEST TEST（M, CO）、`717336` NY FORM TEST（F, NY — NY swap 測試用）、`3226406` BRIAN TEST（無 gender — IncompletePatientInfo 測試用）。
- **測試代碼**：`VAREQUISTION463` = Gut Zoomer（**就是 GZ_EMR_CODE**，happy-path 跟 NY-swap 測試同一產品族）、`485` = GZ-NY、`VAREQUISTION99` = PSA duo（items 376+377，PSAMaleOnly 規則）、`VAREQUISTION89` = Celiac Genetics、`30010` = NutriproZ-Maintenance（ProzFollowupNoPreviousOrder 規則）；Regenere/Skincare `30011-13` 不在 classifier mapping（unrecognized 測試用）。
- **staging 前置 fix（保留中）**：999997 的 LIVE ehr_integrations row（id `cmpcy2u1h0001r107bkwuuuuk`）原本 `ordering_enabled=false`，已改 true — fetchById 硬性要求 LIVE+ordering_enabled，這行解鎖所有後續 API-path staging 測試。
- **Eligibility 實測 failure codes**（vs Confluence 2517139459 有 drift）：實際 `PSAMaleOnly`（文件寫 PFSAMaleOnly）、`IncompletePatientInfo`（會點名缺哪個欄位）、`ProzFollowupNoPreviousOrder`；`GeneticTestAlreadyOrdered` 在 staging 連續下兩單**沒有 fire**（rule 觸發條件待 order team 釐清）。
- **Idempotency 語意**：已全面改版（VP-17497/99/500，2026-07-27）— 見下方「placerId idempotency 完整語意」section；舊的「任何既有 row 都回 duplicate / placerId 永久卡死」行為已不存在。
- **ConfigMap drift 教訓**：PROD ConfigMap `lis-emr-v2-config-prod` 在 E2E 通過前就已是 `ORDER_INTAKE_MODE: live`（違反 PR #206 的 flag 註記）— 「文件說 disabled」不可信，**查實際 ConfigMap**。

## API order path — catalog external code 解析（VP-17475, PR #284, 2026-07-21）

- **API path 的 testCodes = catalog code**（`GUT_ZOOMER` 等，來自 `GET /v1/pricing/item/catalog/products`），**不是** legacy `VAREQUISTION*`。**API-only、無 legacy fallback**（Leo 定調）。HL7 path 不變。
- **解析機制**：`enrich()` classify 前呼叫 pricing `POST /v1/pricing/item/catalog/productMap`（`ProductMapClientService`，per-code TTL cache 30min）→ `{item_id, item_type(packagePriceId|TESTGROUP|bundleId), ...}` → 用 `item_id` join 既有 mapping cache（productMap item_id == legacy `PackagePrice.id`，已實證 845=GZ 5.0）。400 unknown_codes → `unrecognized_test_codes` 乾淨拒單。
- **Auth = platform user JWT**（HS256 `JWT_SECRET`，同 place-order/eligibility）；靜態 `ORDER_API_TOKEN` 會 401 — productMap 跟其他 `ORDER_*_URL` mapping endpoints 的 auth 不同。
- **code→item 的 source of truth = `lis_pricing.external_codes`**（`code, target_type, item_id, promotion_id, shortcut_id, deprecated_at`）。上線初期只有 `GUT_ZOOMER→item 845`；新 catalog code 要 pricing 補 rows。
- **`items.unique_emr_code` 不唯一**（GZ 3.0 與 4.0 都是 `VAREQUISTION279`）— downstream 一律 key on `item_id`/`order_type_id`，別用 unique_emr_code。
- **NY swap 相容**：GUT_ZOOMER→845→VAREQUISTION463，`gz-ny-routing.ts` 的 swap key 就是 463 → catalog 解析後 NY swap 照常觸發（staging E2E 已驗）。
- **未爆彈**：bundleId 的 cache join（`officialBundleIdToBundleMap` key 是 `oldOrderTypeId`，但 productMap 對 bundle 回 `promotion_id`）**未測** — 第一個 catalog bundle code 上線時要驗。**prod 的 productMap endpoint 尚未部署**（404）— prod rollout gated on pricing。Option B（pricing 擁有 composition）另開 VP-17478。

## API order path — placerId idempotency 完整語意（VP-17497/17499/17500，2026-07-27 全數 prod live）

一天內三票連環改版（源頭都是 api-product/Tianhao 的 doc 問答暴露下一層問題），最終語意：

- **Namespace = per-customer（integrator account），不是全域也不是 per-patient**（VP-17499）：`order_intake.customer_id` + 複合 unique `(customer_id, placer_id)`；JWT customer，derive-scope token（VP-17450）在 insert 前 resolve provider 的 customer。**Legacy 全域 unique `order_intake_placer_id_UNIQUE` 已 drop（part B，staging+prod 皆已套用）** — idempotency 完全靠複合鍵；`placer_id_conflict` branch 是 dead code。後續 status 寫入一律用 rowId，不用 placer 字串。
  - 為什麼不 per-patient：idempotency key 識別的是 request；「填錯 patient_id 修正重送」必須落在同一個 key，per-patient scope 會在這個場景雙開訂單。
- **Terminal-failure reclaim**（VP-17497）：`ineligible/rejected/dry_run/failed` 的 row 重送同 placerId = status-gated atomic updateMany 收回重跑 pipeline（保留 row 當 audit trail，不 delete；併發重送恰一個贏）；`received/finalized` 才回 `duplicate`（帶真 sampleId）。
- **Payment replay 防重複收費**：finalize 是 charge-first — `failed` row 可能已完成收費。charge 一回來就 persist 到 order_intake（`payment_id/sample_id_payment/julien_barcode`），reclaim 重跑時經 `parseOrderInfo.sample_id_payment` 走 finalize 既有的 HL7 replay branch 跳過收費。**此路徑 staging 不可 live 測（測試卡全死）— 只有 unit test 蓋著，第一筆 prod customerPay placement-failure retry 要盯**。
- **placerId 是 optional**（VP-17500）：缺席/空白 → server 生成 `AUTO-<uuid>` key = 結構上不可能 dedup，重複呼叫各自下單（portal parity，api-product 決策）；有 placerId 才有完整 idempotency contract。選 AUTO key 而非 nullable 欄位：零 schema churn、row 照留（audit/payment）、MySQL NULL-dup 語意問題整個繞開。
- **Migration 手法（expand/contract 兩段式，值得複用）**：part A 加欄位+複合鍵、**保留**舊全域 unique（線上舊 code 的 idempotency 靠它的 P2002）→ 部署新 code 到兩環境 → part B 才 drop 舊鍵。先 drop = promotion 前 prod 完全沒有防重複下單保護。過渡期跨租戶撞名 fail-closed 422。
- **Cancel endpoint（VP-17517，PR #295/#296 已 merge+promote 至 prod 2026-07-28Z，Jira 仍 Dev To Do）**：POST /order-cancel 包 order-management /orders/cancel；placerId/sampleId 都經 customer-scoped order_intake row resolve（tenancy+API-only 一次搞定；HL7-path 訂單回 order_not_found）；cancelled 是 terminal status、placerId 不可回收；refund 失敗回 `{status:cancelled, refundFailed:true}`。**Gateway route /v1/orders/cancel 尚未由 api-product 配置；staging E2E 未跑**。
- staging E2E 測試資產：patient 3226428（VP17497 ReclaimTest, cust 3194）、samples 2553975/76/79/80、order_intake rows 62/84/85/88。

## SFTP credential 單一來源 — `ehr_vendors`（VP-17385 + VP-17460, 2026-07）

- **教訓（VP-17385 / FOLLOWTHATPATIENT 擱單事故）**：order fetch 曾只讀 legacy `emr_sftp_source`、result push 讀 `ehr_vendors` — 兩套 credential store「靠習慣同步」必然 drift，且失敗模式是**靜默**（folder 每 tick 被跳過，只有 debug-level warn）。**Consolidation > sync discipline**。
- **現況（2026-07-21 完成退役）**：PR #247 先做 vendor-primary + legacy-fallback + drift WARN；VP-17460 PR #277/#278（merged main 2026-07-20）後 fetch path **只讀 `ehr_vendors`**（`loadVendorCredentials`），auto-integrate cred snapshot 也改讀 ehr_vendors（舊的 emrSftpSource query / 1146 地雷已移除）。`emr_sftp_source` 已 **RENAME 成 `emr_sftp_source_retired_20260720`**（staging 3 rows / prod 30 rows 保留；rollback = rename 回來）；07-21 on-prem + AKS 全 pod live-verified 零 table-missing error。
- **收尾 pending**：舒適窗（~1 週）後 DROP retired 表 + `legacy_raw_emr_sftp_source`（零 code refs 的死表）+ 從 schema.prisma 移除兩個 model。
- **表退役手法（可複用，VP-17460 確立）**：(1) 先出 reader-removal PR，deploy 驗證後才動表；(2) **RENAME 而非 DROP** 作 instant-rollback probe，觀察窗過後才 DROP；(3) 驗證 legacy 服務（同 DB 帳號、同 NAT，無法直接指紋）真的下線 → 用 DB 側證據：`hl7_file_input.last_update_pod_name` 60 天 writer census + `SHOW PROCESSLIST` 連線數對照各 service connection-pool size 推算。
- **Key-based auth 已支援**（PR #275, 2026-07-20，BioInsights 首用）：`ehr_vendors.sftp_private_key` / `ehr_integrations.sftp_private_key`（OpenSSH PEM 字串，ppk 要先 `puttygen -O private-openssh` 轉）；order fetch 接受 password-OR-key row，result push pass-through。migration 對 prod（lisportalprod2）要**手動先跑再 deploy**（prod 非 Prisma-managed）。

## Result-ready email deep link（VP-16859 建置 + VP-17474 clinic-scope，2026-07）

- **Token 模型**：`lis_frontend_service.report_email_tokens`（issuance = LIS-setting-consumer；resolve = LIS-transformer `trans-reports.controller.ts`；prod resolve base `/v1/portal/trans-service/trans/deep-link/resolve/:token`）。email href = `portal.vibrant-wellness.com/#/login?report_url=.../r/<24-char-token>`。
- **Resolve outcome → FE 訊息是判別診斷的 key**：`access_denied`（token 找到但無權）=「This account does not have access」；`invalid`（token 查無）=「This link is invalid」。encoding/QP 損壞只可能產生 `invalid`，不可能產生 `access_denied` — 看到 access_denied 直接查登入者身份，別追 encoding（VP-17474 的 QP 理論就是這樣被推翻的）。
- **存取模型（2026-07-22 起 prod live）**：`isRecipient OR isSameClinic` — row 的 `recipient_clinic_id`（issuance 用 email routing 的 `clinic_ids[0]` stamp；legacy 21,444 rows 已用 lis_core_v7 `sample→order_info.clinic_id` backfill）與 JWT `clinic_id` 相等即放行；**cross-clinic 一律 denied（by design）**；legacy NULL-clinic rows 維持嚴格 per-customer check。
- **結構性背景**：result-ready email 常寄到 clinic 共用信箱（office@/info@ — getCustomerEmailBoth 回 clinic-level email），clinic staff 登入常是 `customer_id=null` 的 clinic-role JWT — 舊 per-customer 模型下這群人全部 access_denied，即 VP-17474 誤報的來源。
- 401（JWT guard）不會留 `deep_link_resolve` log（guard 先 throw）；resolve log 有 `login_clinic_id` + `matched_by(recipient|clinic)`，PHI-free。
- **Postmark suppression 必查**：result_ready_new 所在 server 有 16,828 個 suppressed addresses；suppression 中的 clinic inbox 收不到**任何** result-ready email（與任何 outage 無關）。Triage「沒收到 email」先查 `/message-streams/outbound/suppressions/dump`。Postmark server token 可從 noti/notification-center pod env（POSTMARK_KEY）取得。
