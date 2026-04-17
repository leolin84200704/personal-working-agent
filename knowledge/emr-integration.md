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

---

## MSH Value 判定

- **預設**：`msh06_receiving_facility` = customer_id（Provider ID）
- **例外**：ticket 明確寫 "MSH value is the Practice ID" → msh06 = Practice ID
- **BULK UPDATE**：ticket 寫 "update ALL MSH values" → 用 `update-clinic-msh.ts`

---

## Integration Type Rules

| Type | order_clients 需要？ | update-order-clients flag |
|------|---------------------|--------------------------|
| FULL_INTEGRATION | Yes | true |
| RESULT_ONLY | No | false |
| ORDER_ONLY | Yes | true |

- **ticket 未指定 integration type = FULL_INTEGRATION（預設）**
- FULL_INTEGRATION 需要 order_clients + sftp_folder_mapping

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

| Ticket 上寫的 | DB Code（`emr_name` 填這個） |
|--------------|-------------------------------|
| cerbo, mdhq | **MDHQ** |
| charm | CHARMEHR |
| eclinical, ecw | ECW |
| athena | ATHENA |
| follow that patient | FOLLOWTHATPATIENT |
| optimantra | OPTIMANTRA |
| docvilla | DOCVILLA |

`order_clients.emr_name` 必須填 DB Code，不是 ticket 名稱。

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

## 插入後驗證 Checklist

### ehr_integrations
customer_id, clinic_name, clinic_id, msh06, sftp_host, sftp_port, sftp_result_path, sftp_archive_path, sftp_ordering_path, requested_by, status, ehr_vendor_id, legacy_emr_service

### order_clients
customer_name（gRPC）, customer_id, customer_provider_NPI, customer_practice_name, clinic_id, emr_name（DB Code）, remote_folder_path

### sftp_folder_mapping
server_folder, local_folder, emrName
