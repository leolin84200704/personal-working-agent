---
id: ticket-routing
type: ltm
category: pm_patterns
status: active
score: 0.0866
base_weight: 0.7
created: 2026-04-22
updated: 2026-04-22
links: []
tags:
- routing
- ticket
- pm
summary: Ticket keyword to repo/module routing table
---


# Ticket → Repo Routing

> 根據 ticket 關鍵字判斷目標 repo 和模組

---

| Ticket Keywords | Repo | Module |
|----------------|------|--------|
| calendar, schedule, appointment, Google, Outlook, Zoom | LIS-transformer-v2 | `src/calendar/` |
| GraphQL, patient order, merchandise, PNS | LIS-transformer-v2 | `src/trans/` |
| questionnaire, survey, form | LIS-transformer-v2 | `src/questionnaire/` |
| provider setting, 2FA, Twilio, email branding | LIS-transformer-v2 | `src/setting/` |
| patient variable, encounter note | LIS-transformer-v2 | `src/patientvariable/` |
| role, permission, RBAC | LIS-transformer-v2 | `src/role/` |
| vital sign, BMI | LIS-transformer-v2 | `src/vitals/` |
| HL7, transformation | LIS-transformer | `src/trans/` |
| clinic setting, billing, test ordering | LIS-transformer | `src/setting/` |
| EMR, integration, AutoIntegrate | lis-backend-emr-v2 | `src/modules/integration-management/` |
| sample, order, patient (core data) | LIS-backend-v2-coreSamples | `service/` |
| notification, email, SMS, push | LIS-setting-consumer | `src/setting-consumer/` |
| result ready, shipment, kit, billing event | LIS-setting-consumer | Kafka topics |

---

## EMR Integration Tickets 特殊規則

- **"New EMR Integration"** → DB 操作：ehr_integrations + order_clients + sftp_folder_mapping
- **"No results received"** → 先查 `ehr_integrations` 有沒有記錄
- **"Repush results"** → lis-backend-emr-v2 result 推送邏輯
- **"Update vendor list"** / **"Settings EMR vendor"** → `ehr_vendors` 表 + `vendor-management/` module
- **"vendor public/private"** → `ehr_vendors.is_public` 欄位，source of truth 是 Notion EMR Vendor List
- **永遠用 lis-backend-emr-v2**，EMR-Backend 是 legacy
