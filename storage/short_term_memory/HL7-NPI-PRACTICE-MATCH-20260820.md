---
id: HL7-NPI-PRACTICE-MATCH-20260820
type: stm
category: emr_integration
status: active
created: 2026-08-20
updated: '2026-08-20'
links: []
relations:
  unblocked_by: []
  blocks: []
  sibling: [HL7FAIL-20260730-TURNPAUGH, HL7FAIL-20260722-MDHQ, VP-17628]
unblock_when: "抽樣原始 HL7 確認各 vendor 的 practice_id 實際欄位（MSH-4 或其他）後才能排實作；驗證方式：從 SFTP/pod 留存檔抽近 90 天 36 家活躍 clinic 的原始 order 檔，逐 vendor 統計 practice 欄位覆蓋率"
tags: [hl7-order-intake, npi-matching, practice-id, ehr-integrations, inventory, leo-decision]
summary: "Leo 決定：所有 HL7 inbound order 改用 customer_npi + practice_id(clinic_id) 比對，取代現行 ORC-12.1 → customer_id。已產出 prod ehr_integrations 全量 NPI×clinic×vendor 盤點（reference/ehr-integrations-npi-clinic-vendor-20260820.*）：1,154 筆 LIVE+ordering / 889 NPI / 553 clinic，但實際近 90 天只有 36 家 clinic 在送單。新 key 有 126 筆硬 blocker（10 缺 NPI、96 缺 clinic_id、3 格式錯、17 假 NPI）與 151 個撞 key（21 個對到 2 個 customer_id，5 個落在活躍 clinic）。最大未知：inbound practice_id 到底在哪一欄——今天只有 MSH-4 被讀且僅供 logging，msh06 欄位是外送 result 用且 667/1154 存的是 customer_id，不可當對照。"
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
