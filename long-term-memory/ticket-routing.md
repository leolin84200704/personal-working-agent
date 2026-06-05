---
id: ticket-routing
type: ltm
category: pm_patterns
status: active
score: 0.1039
base_weight: 0.7
created: 2026-04-22
updated: 2026-04-22
links:
- rules
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

## Project prefix → 性質
- **VP-** / **VIB-** — feature/bug ticket（PM 維護，sprint planning）
- **LBS-** — LIS Backend Service **Service Desk** project（Zendesk 自動同步）。reporter 常是 `Zendesk Support for Jira` app account，actual requester 在 description / `customerRequestType` 欄位。多半是 prod 線上 hotfix / data fix，due 通常 ≤ 2 天。LBS-1487 案例：Mingxi 透過 Zendesk 報 "endpoint revert + repush order"

---

## PM AC 解讀慣例（Leo / Vibrant）

- **「no silent fallback」≠ 一定要 throw**：PM 通常希望「失敗有 log/audit 軌跡」即可，warn log + sweep 既有 fallback path 也算 graceful。VP-16416 驗證：Leo 推翻 strict throw 改 `logWarn` + fall through。實作時若 ticket 描述模糊，預設 graceful fallback + warn log，不要直接 throw 中斷 caller。
- **Step 4 呈報格式**：列細節問題時要**同步給出我的 default 偏好**（「以下我採 X，若不同意可調整」），不要只列多選項給 PM 選 — 多選項格式會讓 PM 只答主問題、忽略細節，導致回頭修一輪。
- **Epic 下 ticket dependency 反向是常態**：本應先做的 dependency ticket 可能 due date 在後（例 VP-16165 due 5/8 但其依賴的 VP-16164 due 5/15、VP-16166 due 5/13）。Step 2 一定用 JQL `parent = <epic>` 列出 sibling 全貌，不要只看單張 ticket 的 due date 推斷可獨立交付。
- **Step 4 至少 propose 一個「最小可獨立交付片」選項**：Leo 偏好把 ticket 切成「不依賴任何 sibling 的 thinnest slice」做完先交，剩下 ACs 等 dependency ticket 完成後再補。VP-16165 驗證：原本以為要做完整 4-step cascade，Leo 拍板只做「fallback 替換」一段。呈報 A/B 兩極方案時主動補 C「最小切片」。
- **Leo 偏好 SQL 用 LIS 內部 ID（FK）而非衍生欄位**：例 `ehr_integrations.clinic_id` 優於 `msh06_receiving_facility`。內部 ID 通常有 index、不受歷史回填殘留影響、未來遷移時改名成本低。寫 SQL 時若可選 FK vs 衍生欄位，預設選 FK。VP-16165 驗證。
- **PM 「only X, not Y」→ narrow exclusion of Y, NOT broad inclusion of X**：VP-16612 案例，PM 講 "only providers, not Clinical Team"。我提 `role === 'provider'`（broad inclusion），Leo 改成 `!(practice_id=150105 AND role='clinicadmin')`（narrow exclusion）。差異：我的版本默默把 patient role 也排除掉；Leo 的版本只動 Y、其他角色維持原狀。**rule**: 把 PM 的「排除誰」翻成程式邏輯時，預設用 `!(條件)` 排除 Y，不要用 `=== X` 限制成只允許 X。前者保留 unconstrained 集合，後者會 silently change 未提及的 case。
- **PM 「在 X field 加上 Y」→ 把 Y 嵌進 X 的 VALUE，不要新增 paired field**：VP-16664 案例，PM 講「每個時間 field 加上 timezone」。我提加 `*_timezone` paired YAML field（broad schema change）→ Leo 立刻拒絕 "不能改 yaml file 啊, email template端什麼都沒改"。正解：embed TZ abbrev 在既有 field value 裡（`consult_time: "10:30 AM PDT"`），YAML schema 不動。**rule**: PM 講「加上某資訊」時，預設「enrich existing field's value」，不要「add new paired field」— 後者會被視為改 template/API 的外部 contract。YAML field schema 對 PM 來說 = email template body 的一部分，加 field 就是改 template，需要明確 OK。

- **VP-16163 (EHR Integration V2) epic ticket 的 body/AC 常從 quarantine PRD 段誤抄，title 才準**：VP-16629（title=「approve/reject integration requests」、body 卻整段 quarantine resolution，實際做 ehr_integrations approve/reject）+ VP-16760（同樣 body=quarantine/provisional、AC 寫 resolved_by/resolution_action，實際是 `ehr_vendor_inquiry`「Not on the list」approve/reject）兩例確認。disambiguation 訊號優先序：**title > `split from` issue link > reporter/Leo comment > body**。遇到 body 講 quarantine/provisional 但 title 講 approve/reject，**先信 title、跟 Leo 確認，別照 body 硬做 quarantine**（quarantine 真正歸 VP-16166 + provisional 歸 VP-16168，多半還沒 ship）。

## EMR Integration Tickets 特殊規則

- **"New EMR Integration"** → DB 操作：ehr_integrations + order_clients + sftp_folder_mapping
- **"No results received"** → 先查 `ehr_integrations` 有沒有記錄
- **"Repush results"** → lis-backend-emr-v2 result 推送邏輯
- **"Update vendor list"** / **"Settings EMR vendor"** → `ehr_vendors` 表 + `vendor-management/` module
- **"vendor public/private"** → `ehr_vendors.is_public` 欄位，source of truth 是 Notion EMR Vendor List
- **永遠用 lis-backend-emr-v2**，EMR-Backend 是 legacy
