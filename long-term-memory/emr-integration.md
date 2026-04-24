---
id: emr-integration
type: ltm
category: emr_integration
status: active
score: 0.2599
base_weight: 1.0
created: 2026-04-22
updated: 2026-04-22
links:
- VP-14787
- VP-15952
- VP-16014
- VP-16175
- VP-16193
- VP-16245
- VP-16251
- VP-16271
- VP-16280
- VP-16289
tags:
- emr
- hl7
- integration
- provider
- practice
summary: EMR/HL7/SFTP integration rules, identity mapping, MSH values, bundle config
---















# EMR Integration Rules

> Single source of truth. Consolidated from VP-15874, VP-15979, VP-15791, VP-15980, VP-15955.

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

---

## Known Script Bugs

### insert-order-client.ts
- **Bug**: customer_id 會被設為 clinic_id 值（Practice ID）而非 Provider ID
- **影響**: order_clients.customer_id 錯誤
- **Workaround**: 執行後必須驗證 customer_id，錯誤時手動 SQL 修正:
  `UPDATE order_clients SET customer_id = {provider_id} WHERE id = {record_id}`

### insert-ehr-integration.ts
- 當 DB 已有相同 customer_id 的記錄時（如 PENDING 狀態），script 會拒絕插入
- **Workaround**: 改用 Prisma update 或 raw SQL 更新現有記錄
- Script 需要 ehr_vendors 中存在 vendor code，新 vendor 必須先加入 ehr_vendors 才能使用
- **MDHQ 已知問題**: `sftp_ordering_path` 不會被設定（null）、`sftp_archive_path` 缺尾部 `/`、`sftp_folder_mapping.sftp_source_id` 為 null — 每次需手動修正

---

## Same Practice — Follow Existing Integration

同 practice 新增 provider 時，下列欄位**必須抄 same-clinic 既有 integration 的值**（不是 knowledge 預設）：

| 欄位 | 所在 table | 預設（fallback） | 備註 |
|------|-----------|------------------|------|
| `report_option` | `ehr_integrations` | `PERSONALIZED` | script 已自動處理（`getReportOption(clinicId)`） |
| `kit_delivery_option` | `ehr_integrations` | `NO_DELIVERY` | **script 未處理，需手動補** |
| `old_clinic_id` | `order_clients` | `null` | **script 未處理，需手動補**；同 clinic 的既有記錄通常共用同一個 legacy clinic id |

```sql
-- 一次撈齊所有 follow-existing 欄位
SELECT report_option, kit_delivery_option FROM ehr_integrations WHERE clinic_id = {practice_id} LIMIT 1;
SELECT old_clinic_id FROM order_clients WHERE clinic_id = {practice_id} AND old_clinic_id IS NOT NULL LIMIT 1;
```

- 若 same-clinic 無既有 → 套上表 fallback
- **注意**: `integration_type` **不** follow 既有，仍套預設 FULL_INTEGRATION（見「Integration Type Rules」）

- **`sftp_folder_mapping` 可能已存在**: 同 practice 的其他 provider 若先建過 integration，ORDER mapping 通常已經在 `sftp_folder_mapping`，insert script 會直接跳過。新增 provider 前先查，避免誤以為 script 失敗。

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

## Vendor File Size Limits

| Vendor | Limit | 建議閾值 |
|--------|-------|---------|
| Cerbo (MDHQ) | 15MB | 14MB |
| ECW | 20MB | 18MB |
| Epic | 25MB | 23MB |

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

---

## 插入後驗證 Checklist

### ehr_integrations
customer_id, clinic_name, clinic_id, msh06, sftp_host, sftp_port, sftp_result_path, sftp_archive_path, sftp_ordering_path, requested_by, status, ehr_vendor_id, legacy_emr_service, **report_option（same-clinic follow）**, **kit_delivery_option（same-clinic follow）**

### order_clients
customer_name（gRPC）, customer_id, customer_provider_NPI, customer_practice_name, clinic_id, emr_name（**DB Code 原始大小寫**，如 `MDHQ` 非 `mdhq`）, remote_folder_path, **old_clinic_id（same-clinic follow）**

### sftp_folder_mapping
server_folder, local_folder, emrName
