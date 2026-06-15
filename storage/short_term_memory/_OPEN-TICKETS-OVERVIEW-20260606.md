---
id: _OPEN-TICKETS-OVERVIEW-20260606
type: stm
category: process
status: reference
score: 0.0656
base_weight: 0.6
created: 2026-06-06
updated: 2026-06-06
links: []
tags:
- overview
- batch-dialectic
- open-tickets
- routing
summary: 跨 ticket 總覽（2026-06-06 批次分工辯證，48 張 open ticket）：分組 / 依賴 / Dev Blocked 解鎖
  / 需 PM 確認 / 建議處理順序。各 ticket 完整解法見同目錄 {KEY}.md。
---



# Open Tickets — 批次分工辯證總覽

> 生成：2026-06-06 | 48 張 open ticket（assignee=Leo）| 96-agent workflow（5.9M tokens）
> 每張 ticket 的完整解法見同目錄 `{KEY}.md`。本檔為跨 ticket 總覽：分組、依賴、Dev Blocked 解鎖、需 PM 確認、建議處理順序。

## 統計
- Effort 分布：S=31, M=11, L=6
- Confidence 分布：5★=11, 4★=36, 3★=1
- 需 PM/vendor 確認才能動的：46 張 → LBS-1547, VP-16832, VP-16516, QH-919, VP-16885, VP-16514, QH-5840, VP-16513, VP-16169, VP-16168, VP-16172, LBS-1541, VP-15279, VP-16787, VP-16786, VP-16785, VP-16784, VP-16685, VP-16164, VP-16759, QH-5409, VP-16166, QH-3752, QH-2577, QH-4352, VP-16186, QH-4350, QH-3324, QH-1130, QH-2259, QH-2648, QH-680, QH-1591, QH-918, QH-2257, QH-1860, QH-686, QH-1159, QH-1660, QH-1775, VP-9299, QH-1104, QH-862, QH-824, QH-610, QH-211

## 分組與各 ticket 一句話解法

### Practice-Level Integration epic (7)
- **VP-16168** [L/4★] ⛔Blocked ❓PM：Identity Resolution 的 Step 4：當 inbound HL7 order 的 sending facility 對到 practice，但 provider NPI 在系統找不到對應 provider 時，自動建一筆 provisional_providers、為該 order 標記 quarantine，並依該 practice 的 auto_enroll_new_providers 設定決定走 auto-enroll（建 PENDING_APPROVAL membership）或通知 practice admin 手動加。
- **VP-16169** [L/4★] ⛔Blocked ❓PM：Phase-3 notification layer of EHR Integration V2 epic (VP-16163). Auto-send email + write an in-app portal banner at three event points: (A) provisional provider created under an integrated practice -> Template #4 to practice admin(s) + Template #5 to internal team; (B) provider_integration_memberships.status transitions to active -> Template #6 to practice admin(s) + the provider (if a Portal account exists); (C) 3 business days after Trigger A with no admin response -> resend #4/#5 with a "Reminder:" subject prefix. Recipients, Postmark template IDs (per VP-16178), idempotency guards, and per-send audit logging are all in scope.。
- **VP-16172** [L/4★] ⛔Blocked ❓PM：Epic VP-16163 將 EHR integration 從 provider-level 提升到 practice-level + per-provider membership。
- **VP-16164** [M/4★] ⛔Blocked ❓PM：建立 EHR Integration V2 的 practice-level 資料模型（practice_integrations / provider_integration_memberships / vendor_provider_fields 三張新表），把既有 provider-level ehr_integrations 依 clinic_id + vendor 分組 backfill 進去，作為 epic VP-16163 下 VP-16168（Provider Detection）/ VP-16172（Practice Admin RBAC）/ VP-16169（Notification）的 schema 基礎。
- **VP-16166** [M/4★] ⛔Blocked ❓PM：當整合中介層收到無法辨識 provider 的 HL7 order 時，不再只 log 丟棄，而是把整封原始 HL7 完整寫進新的 quarantined_orders 表（永不遺失訊息），由 UniMod admin 審核 resolve（link 既有 provider / 建新 provider / reject）。
- **VP-16885** [M/4★] ⛔Blocked ❓PM：讓 practice admin 在「邀請新成員」modal 勾一個 optional checkbox (enrollToEHR)，把被邀請的 provider 一併報名進該 practice 的 EHR integration，省去事後到 portal Third-party Integration 手動設定。
- **VP-15279** [S/4★] ❓PM：讓 Staff+Delegate 員工代 provider 操作時，系統能記錄 provider-of-record 與實際操作人，並用 delegation link 驗證授權（audit / attribution，AC4 防止 staff 用自己身分下單）。

### Meeting Type feature (3)
- **VP-16832** [L/4★] ⛔Blocked ❓PM：當 EMR 進來的 order 含 Gut Zoomer (GZ) 且病人地址州別為 NY，且該 clinic 在 beta 名單內時，自動把 GZ battery code 換成 GZ-NY、加 $80 NY processing fee，並寄一封 gz-ny-emr-swap-provider 確認信給 ordering provider（只插值 {{patient_state}}，不含其他 PII）。
- **VP-16512** [S/4★]：在 calendar PostgreSQL（DATABASE_URL_CALENDAR）建 3 張全新表（v2_meeting_type / v2_meeting_type_weekly_availability / v2_meeting_type_date_specific_hour），承載 provider-level multi-type 預約（Epic VP-15817），與既有 practice-level v2_practice_event_type 並存。
- **VP-16514** [S/5★] ⛔Blocked ❓PM：Provider 在 Doctor Portal 管理自己的多種 meeting type（epic VP-15817 / VP-15817 "EHR Calendar - Multi-Type Availability"）：(a) 可停用某 type 而不刪歷史預約，(b) 可拖拉排序顯示優先序，且這些變更要反映到病患端 public booking 頁（inactive 排除、依 display_order 排序）。

### RPC cloud migration (7)
- **VP-16787** [L/4★] ❓PM：將 transv2 的 AUDIT gRPC client 從 on-prem (192.168.60.6:32700) 遷移到 cloud (lis-auditlog-grpc-service.default.svc.cluster.local:30113)，使所有 Calendar/EMR audit 路徑以 cloud 為 primary，並補齊缺失的 AUDIT_RPC_CLOUD config 注入（此為 parent VP-16685 卡 Dev Blocked 的真正部署缺口）。
- **VP-16685** [M/5★] ⛔Blocked ❓PM：Under epic VP-16776 (Cloud Migration - EMR), move Trans V2 Calendar (LIS-transformer-v2) and EMR (lis-backend-emr-v2) off on-prem 192.168.60.6 dependencies onto cloud interfaces so both services can run on AKS. Per Leo's 2026-05-22 comment the scope was deliberately narrowed to gRPC RPC migration only; Redis and Kafka/Event Hub migration are explicitly excluded as too risky at this stage. The ticket is now an umbrella whose only remaining work is the 4 RPCs split into VP-16784/85/86/87.。
- **VP-16784** [M/4★] ⛔Blocked ❓PM：把 SHIPPING_RPC gRPC client 從 on-prem (192.168.60.6:31865) 指向 cloud in-cluster gRPC service (lis-shipping-service-grpc.shipping.svc.cluster.local:63142)，作為 parent VP-16685 / epic VP-16776 (Cloud Migration - EMR) 的一片。
- **VP-16785** [M/4★] ❓PM：把 IssueService gRPC client 從 on-prem ISSUE_RPC (192.168.60.6:30071) 重新指向 cloud in-cluster endpoint lis-issue-system-service.issue.svc.cluster.local:30071，移除 on-prem 依賴。
- **QH-1159** [S/4★] ❓PM：QA 驗證任務（QA Hub project，status=To Do），是 dev story VP-13935「Update calendar module to use v2 rpc endpoint」(Done, P1) 的 is-tested-by 對應票。
- **QH-1775** [S/5★] ❓PM：QH-1775 是 QA Hub 的 QA 驗收 ticket，由 Automation 從 VP-14295 自動建立（issue link type=Test：QH-1775 tests VP-14295）。
- **VP-16786** [S/4★] ❓PM：把 transformer-v2 的 dashboard gRPC client 指向 cloud in-cluster service (lis-dashboard-prod-rpc-service.default.svc.cluster.local:5800)，作為 EMR/Calendar 上 AKS 遷移 (epic VP-16776) 的一環。

### EMR 維運 / 整合 ops (11)
- **LBS-1541** [M/4★] ⛔Blocked ❓PM：當 EMR-originated order 含 ticket 列出的約 20 個 trigger package（Wheat Zoomer、各 Food/Lyme/Coinfections/Neural Zoomer Plus、Food Bundle、Food Zoomer 等）任一個時，自動掛上 "Total Immunoglobulins" 作為 $0 免費 add-on，行為對齊 VA consumer portal（描述中的 "like VA"）。
- **QH-1660** [S/4★] ❓PM：QH-1660 is an auto-created QA mirror of bug VP-14195 (issuelink type=tests). Its own description is empty ("Auto-created from VP-14195"); all substance lives in VP-14195. The underlying ask: Cerbo order #0000054091 for patient Susan Parris (placed 12/2) was not appearing on her Vibrant profile — confirm whether the order was received, why it didn't attach, and how to resolve. VP-14195 is already Done as a business (non-code) resolution. QH-1660's only valid action is QA verification of the live state, then close to align with VP-14195. No development is needed.。
- **QH-2257** [S/4★] ❓PM：QH-2257 是 VP-14748 的 auto-clone QA 鏡像（issuelink type=Test/「is tested by」），description 只有 smartlink、無實質內容。
- **QH-2577** [S/3★] ❓PM：Re-push the latest (TNP-marker-removed) version of report 2511046917's HL7+PDF to the provider's EMR via SFTP, then confirm the file the provider receives no longer shows TNP markers. The work is a re-execution/verification of the source ticket VP-15050 (Zendesk via Xinyue Lai): provider still saw TNP markers in EMR while the portal already showed them removed, implying the previously pushed EMR file was a stale version.。
- **QH-3752** [S/4★] ⛔Blocked ❓PM：QA-verify (sign-off) that the EMR result-sending API already implemented under VIB-1641 (Done 2026-03-11) behaves correctly: generate HL7 from a sample's results, optionally transmit to the vendor SFTP, with the classic/personalized report toggle. QH-3752 is a QA Task that "tests" VIB-1641; both Jira descriptions are empty auto-create stubs, so this is a verification + documentation task, NOT new development. PM/Leo must confirm the deliverable and whether any VIB-1641-uncovered requirement exists before work proceeds.。
- **QH-4350** [S/4★] ❓PM：QH-4350 是 QA-Hub 鏡像/驗收票（description 直接寫「Auto-created from VP-16010」、is tested by VP-16010），不是獨立工程任務。
- **QH-4352** [S/5★] ❓PM：QH-4352 是 QA Task，由 BE Story VP-16014（issuelink type="Test"/"is tested by"，VP-16014 已 Done）自動產生。
- **QH-4608** [S/5★]：QA-verify that the Optimantra x Practice 6338 (The Epigenetics Healing Center / Provider Jay Goodbinder, customer_id 5408) FULL_INTEGRATION shipped under VP-16193 (Done) is correct in prod and that the practice can receive and approve samples (the two VP-16200/VP-16201 subtask ACs). This is a QA close-out task, not a dev task — no code to write.。
- **QH-5409** [S/5★] ❓PM：讓 FE 在 local env 開發時打 EMR auto-integrate API 不被瀏覽器以 CORS/preflight 擋住。
- **QH-5840** [S/4★] ❓PM：驗證 EMR integration API 的 CORS error 是否已修復（QA pass/fail），而非重寫 fix。
- **VP-16186** [S/4★] ❓PM：把 VP-15659 開發的「依 patient_id + 時間範圍取 HL7 lab content」read-only API 接上真實生產資料並驗證能取到真資料。

### Calendar / Clinical (9)
- **VP-16516** [L/4★] ⛔Blocked ❓PM：讓每個 meeting type 擁有自己的可約時段（weekly hours + date-specific overrides），取代目前全 provider 共用單一套 availability；並提供「Apply default availability」一鍵把 provider 預設班表（v2_schedule）複製進 meeting type。
- **VP-16513** [M/4★] ❓PM：讓 provider 或 same-practice admin 透過 REST 對自己的 provider-level meeting type 做 CRUD：create 自動產 unique slug + booking URL、list 預設只回 active、partial update、soft delete 保留歷史 booking、ownership 授權（401/403）。
- **LBS-1547** [S/4★] ⛔Blocked ❓PM：將某位 Vibrant Clinical Team clinician（practice 150105）的 clinical consultation 收信 email 改為 caroline@doctorcaroline.com，使其後續 booking confirmation 與 reminder email 寄到正確信箱。
- **QH-1591** [S/4★] ❓PM：QH-1591 是 QA Hub 的 mirror ticket，由已 Done 的 Story VP-14142 經 "tests/is tested by" link auto-create，description 只有一行 smartlink，無 AC、無 subtask，assignee 是 Leo。
- **QH-2259** [S/4★] ❓PM：QH-2259 是 VP-14750（Story, Done）的 QA 鏡像票（link type "is tested by"，同標題），本身狀態 To Do、body 僅 "Auto-created from VP-14750"、三則 comment 全是 Automation for Jira 回音。
- **QH-2648** [S/4★] ⛔Blocked ❓PM：QH-2648 是 QA Task，由 Automation 從 Story VP-15115（同名，已 Done 2026-02-11）以 Test link 自動建立（QH-2648 tests VP-15115）。
- **QH-3324** [S/5★] ❓PM：驗證 Clinical Consult（practice 150105）的活動建立已放寬「必須同時有 Provider+Patient」的限制，改為「至少一個參與者即可」，以支援 block-out time / staff meeting 等場景。
- **QH-680** [S/5★] ❓PM：QH-680 是一張 QA Task，是 dev story VP-13527「Add oauth」(Story/P1/Done) 的測試對應票（issuelink type = is tested by）。
- **VP-16759** [S/4★] ⛔Blocked ❓PM：FE Patient Profile redesign (QH-4511) runs on a Cloudflare preview origin (*.va-portal.pages.dev) and calls GET /dashboard/user/timeline on staging, which returns 403, blocking the timeline section and failing QA. Goal: make staging getTimeline return 200 for this FE flow. NOTE: ticket is Dev Blocked and the only hard blocker is missing repro data (URL/payload/token) — Leo already requested it on 5/29 and QA has not responded.。

### TransV2 rewrite / doc / test (8)
- **QH-1130** [M/4★] ⛔Blocked ❓PM：QH-1130 是 QA Hub 的 QA Task，唯一連結為 `is tested by VP-13906`（[BE] Transv2 Refactor/Document/Test - Utility module 2nd Batch，已 Done/Dev Complete，交付者 Fan Zhou）。
- **QH-918** [M/4★] ⛔Blocked ❓PM：QH-918 是 QA Hub 自動鏡像 ticket（`tests` → VP-13758，已 Done）。
- **QH-919** [M/4★] ⛔Blocked ❓PM：QH-919 是 QA Hub 鏡像票，真正開發票是 VP-13759 (Story, P3, Dev To Do)，父 epic VP-13757「Transv2 Batch 2」目前 Dev Blocked。
- **QH-1104** [S/4★] ⛔Blocked ❓PM：QH-1104 是 QA Hub board 上 VP-13889（BE Story, P0, Done）的測試鏡像（issuelink type=Test，"is tested by"），description 只有 auto-created from VP-13889，無自有 AC。
- **QH-211** [S/5★] ❓PM：為 coreSamples gRPC service 的 sample-attribute 檢查 RPC 補一份 API contract 文件,讓 QA/前端/整合方知道如何呼叫、輸入輸出語意與邊界行為。
- **QH-610** [S/4★] ❓PM：QH-610 是 QA Task，由已 Done 的 Story VP-13464 (is tested by) auto-mirror 而來，title 相同、description 全空（只有 auto-link）。
- **QH-686** [S/4★] ⛔Blocked ❓PM：QH-686 是 QA Task，由 Jira automation 從 VP-13533「Add more endpoints to calendar」(Story/P1/Done) auto-create，issuelink type=Test（QH-686 is tested by VP-13533）。
- **QH-824** [S/4★] ❓PM：QA Task mirroring VP-13671 (Done, P0 — itself a "Create Doc" story, NOT a code-feature story). The deliverable is to verify the Confluence docs for VP-13671's three calendar deliverables (getClinic, clinic-location CRUD, getCanceledMeetingRequests) exist, are accurate against the current resolvers, and are consumable by FE/integration. No code or DB work. Ticket description is only an auto-smartlink; real scope lives in VP-13671.。

### Notification / Email (1)
- **VP-9299** [S/4★] ❓PM：When the "result ready" email is sent to the customer, the product_list field must be built from the V2 endpoint (base-report-service/result/getReportStatusListV2?barcode=) instead of the legacy getReportStatusList. The ticket body is a one-liner with example barcode 2410246397, no AC. Net effect: same email, product names sourced from V2.。

### Infra / DevOps (1)
- **QH-862** [S/5★] ❓PM：讓 AKS 能對 transv2 pod 做健康 gating：liveness 失敗重啟 pod，readiness 失敗暫時移出 Service endpoint。

### 其他 (1)
- **QH-1860** [S/5★] ⛔Blocked ❓PM：這是一張非程式碼的 onboarding 任務，由 Automation for Jira 從 VP-14383（同名 [BE] Get Familiar with EMR，狀態 Done）自動鏡射到 QA Hub。

## 依賴關係（誰擋誰 / 同 epic）
- LBS-1547 → 依賴/關聯：VP-16413 (同一 clinical-consult email 資料域，已驗證 calendar_owner_email 為收件來源), VP-16384 / VP-16391 (Clinical Consult Calendar epic, practice 150105，同資料域但無 code 依賴)
- VP-16832 → 依賴/關聯：VP-16670, QH-5798, VP-16169
- VP-16516 → 依賴/關聯：VP-16512, VP-16513, VP-16514, VP-15817, QH-5238
- QH-919 → 依賴/關聯：VP-13759, VP-13757, QH-1130, QH-918
- VP-16885 → 依賴/關聯：VP-16164, VP-16168, VP-16172, VP-16887, QH-5842, VP-16890
- VP-16514 → 依賴/關聯：VP-15817, VP-16512, VP-16513, VP-16516, QH-5236
- QH-5840 → 依賴/關聯：VP-16878, QH-5409, VP-16627, VP-16009
- VP-16512 → 依賴/關聯：VP-15817, VP-16513, VP-16514, VP-16516, QH-5234
- VP-16513 → 依賴/關聯：VP-16512, VP-16514, VP-16516, VP-16518, QH-5235, VP-15817
- VP-16169 → 依賴/關聯：VP-16168, VP-16164, VP-16178, VP-16172, VP-16170, VP-16163, QH-4566
- VP-16168 → 依賴/關聯：VP-16164, VP-16166, VP-16169, VP-16172, VP-16507, VP-16885, VP-16163, QH-4565
- VP-16172 → 依賴/關聯：VP-16164, VP-16168, VP-16169, VP-16170, VP-16163, QH-4569
- LBS-1541 → 依賴/關聯：VP-16685, VP-16784, VP-16785, VP-16786, VP-16787
- VP-15279 → 依賴/關聯：VP-15274, VP-15311, QH-3183, VP-15128, VP-15314
- VP-16787 → 依賴/關聯：VP-16685, VP-16776, QH-5727, VP-16784, VP-16785, VP-16786
- VP-16786 → 依賴/關聯：VP-16685, VP-16776, VP-16784, VP-16785, VP-16787, QH-5726
- VP-16785 → 依賴/關聯：VP-16685, VP-16776, QH-5725, VP-16784, VP-16786, VP-16787
- VP-16784 → 依賴/關聯：VP-16685, VP-16776, VP-16785, VP-16786, VP-16787, QH-5724
- VP-16685 → 依賴/關聯：VP-16776, VP-16784, VP-16785, VP-16786, VP-16787, QH-5522, VP-15460
- VP-16164 → 依賴/關聯：VP-16163, VP-16168, VP-16172, VP-16169, VP-16166, VP-16793, VP-16794, VP-16795, VP-16273, QH-4561
- VP-16759 → 依賴/關聯：QH-4511, QH-5840, QH-5409, VP-16685
- QH-5409 → 依賴/關聯：VP-16627, VP-16878, QH-5840
- VP-16166 → 依賴/關聯：VP-16163, VP-16164, VP-16168, VP-16169, VP-16172, VP-16685, QH-4563
- QH-3752 → 依賴/關聯：QH-2577, QH-1775, QH-4350, QH-2257
- QH-2577 → 依賴/關聯：VP-15050, QH-1775, LBS-1487
- QH-4352 → 依賴/關聯：VP-16014, VP-16261
- QH-4608 → 依賴/關聯：VP-16193, VP-16200, VP-16201
- VP-16186 → 依賴/關聯：VP-15659, QH-4590, VP-14704, VP-16685
- QH-4350 → 依賴/關聯：VP-16010, VP-15948, VP-15941, VP-15938, VP-15410
- QH-3324 → 依賴/關聯：VP-15374, VP-14857, VP-15051, QH-2648, QH-1159, QH-1591, QH-2259
- QH-1130 → 依賴/關聯：VP-13906, VP-13757, QH-919, VP-13759
- QH-2259 → 依賴/關聯：VP-14750, VP-14656
- QH-2648 → 依賴/關聯：VP-15115, VP-16361, VP-16410, VP-16499, VP-16520, VP-16521, VP-16685, QH-824
- QH-680 → 依賴/關聯：VP-13527, QH-1159, QH-1591, QH-2648, QH-824, QH-918, QH-919, QH-1130
- QH-1591 → 依賴/關聯：VP-14142, VP-16685, VP-16512, VP-16513, VP-16514, VP-16516, QH-1159, QH-2648, QH-824
- QH-918 → 依賴/關聯：VP-13758, VP-13757, VP-16759, VP-16786, QH-919, QH-1130
- QH-2257 → 依賴/關聯：VP-14748
- QH-1860 → 依賴/關聯：VP-14383
- QH-686 → 依賴/關聯：VP-13533
- QH-1159 → 依賴/關聯：VP-13935, VP-16685, VP-16784, VP-16785, VP-16786, VP-16787, QH-824, QH-2648, QH-1591
- QH-1660 → 依賴/關聯：VP-14195, VP-14238
- QH-1775 → 依賴/關聯：VP-14295, QH-2577, QH-3752
- QH-1104 → 依賴/關聯：VP-13889, VP-13873, VP-13874, VP-16759
- QH-862 → 依賴/關聯：VP-13703, VP-16685, VP-16787, VP-16786, VP-16785, VP-16784
- QH-824 → 依賴/關聯：VP-13671, QH-211, QH-1130, QH-918, QH-919
- QH-610 → 依賴/關聯：VP-13464
- QH-211 → 依賴/關聯：VP-13142, QH-824, QH-919, QH-918, QH-1130

## Dev Blocked 解鎖建議

**LBS-1547** (Update Clinical Consultation Email Address)
  - 非硬 dev block，而是需求/識別資料缺口：description 僅提供 Zendesk request ID 2605196651 與目標 email，缺少可定位 v2_calendar row 的 LIS 內部識別碼。Unblock = 從 Zendesk Support tab 取得 requester 的 clinician 全名/clinic/舊 email，最佳是內部 calendar_owner_id，即可用 @@unique(practice_id, calendar_owner_id) 唯一定位後執行單列 UPDATE。

**VP-16832** ([BE] EMR — Auto-Swap GZ to GZ-NY & Trigger Email)
  - Dev Blocked 主因為需求 7 項 unknown 未解 + FE Postmark 3 模板 prerequisite 未完成。Unblock 需 PM (Xiaoye Li) 回覆已在 ticket comment（2026-06-05）列出的 7 點，最關鍵：(1) GZ / GZ-NY 的確切 uniqueemrcode + GZ-NY 是否已 seed +$80 fee；(2) 'beta tag' 是否即 repo 既有 per-clinic beta_programs 機制、其 gating 意圖（gradual rollout / per-customer opt-in / kill switch）；(3) gz-ny-emr-swap-provider 的 Postmark TemplateId 與對接路徑（自接 / 共用 VP-16169 / Vibrant 端點）；(5) 'ordering provider email' 來源（contact_email vs ORC NPI）。建議直接開 call。階段一 swap+gate 可在 (1)(2)(5) 釐清後先獨立交付，不必等 email prerequisite。

**VP-16516** ([BE] Meeting Type-Scoped Availability (Weekly Hours & Date Overrides))
  - 非技術阻塞，是 scope/design 待確認。Leo 自己的 comment（2026-06-05）：整個 epic 把系統從 clinic/practice-level（一 practice 一組 appointment type、一 provider 一套 availability、public booking 走 Practice→Provider）轉成 per-provider meeting type + 各自 availability，而本 ticket 還要改全客戶共用的 slot-calculation 引擎，屬於 scope/design 變更，已要求 sync call 確認方向。解除方法：等 sync call 拍板大方向（per-provider 是否確定、舊 clinic-level 系統並存策略），確認後按 B/C 先做零風險的 Part 1，Part 2 待大方向 + VP-16512/16513 merge 後再做。STM 已記錄 paused、未開 branch、無 commit。

**QH-919** ([BE] Transv2 Rewrite/Document/Test - Utility module 1st Batch)
  - QH-919 本身為 To Do、不算 blocked，但其開發票 VP-13759 的父 epic VP-13757「Transv2 Batch 2」是 Dev Blocked，PM Xiaoye Li 2025-12-08 留言原因為排程/容量（Unable to accommodate in this sprint; rescheduled），非技術 blocker。Unblock 路徑：方案 A 的 test+doc 切片不依賴任何 sibling，可立即動工繞過 epic 排程 block；待 PM 釐清 1st Batch 範圍後即可開始。

**VP-16885** ([BE] Support EHR enrollment flag on invite)
  - 不是真正 Dev Blocked（DB 表已 live）。實務上有兩個前置: (1) PM 確認 epic 列的 Medium-risk 問題（見 clarifyingQuestions），(2) emr-v2 需先把 VP-16164 的 PracticeIntegration/ProviderIntegrationMembership Prisma model + committed migration 補進 repo（表已存在 prod/staging，只缺 Prisma 定義）。dev start 6/22 (Sprint 22)，現為分析交付階段。

**VP-16514** ([BE] Meeting Type Status Toggle & Reorder Endpoints)
  - 非真正 blocker（Dev To Do 狀態合理）。code 已 commit 屬實，卡點是流程：(1) 與 VP-16513 同 branch/PR #485 尚未收尾；(2) AC2/AC3 public 反映歸屬未跟 PM 敲定（且 VP-16516 並非承接者，需新建 subtask 或明確指派）；(3) 缺 unit test。解法：先跟 PM 確認 public 歸屬與 AC4 放寬授權，補 toggle/reorder unit test，prisma generate + start:dev 過後 PR 進 stage_test 驗收。

**VP-16169** ([BE] Dual Notification System - Email Triggers)
  - Real status is Dev To Do, but the trigger-wiring ACs are hard-blocked: Trigger A needs the provisional_providers table (VP-16168) + its notified_practice_at/notified_internal_at idempotency columns, and Trigger B needs the provider_integration_memberships table + active-status transition hook (VP-16164). Neither table exists in the emr-v2 schema (0 grep hits). Unblock path: (1) start Method B now (send methods + resolvePracticeAdmins + audit log + @Cron skeleton are NOT blocked); (2) connect Trigger A/B call-sites the moment VP-16168 and VP-16164 merge; coordinate so VP-16168 ships the idempotency timestamp columns. Note: scheduler is NOT a blocker -- @nestjs/schedule + node-cron already in repo (scheduled-reports module), correcting the engineer's claim that Trigger C needs new infra.

**VP-16168** ([BE] New Provider Detection Engine & Provisional Provider Records)
  - Live Jira 顯示 Dev Blocked，且 is-blocked-by VP-16164 link 仍 active（VP-16164 本身也 Dev Blocked）。真正卡點：VP-16164 的 Prisma model 仍只在 feature/leo/VP-16164，未 merge 進 stage_test（git merge-base 確認非 HEAD ancestor），base branch schema 完全沒有 PracticeIntegration/Membership/VendorProviderField，故 AC3-5 無 model 可寫。注意 Jira automation 把 VP-16468（transfer order，已 Done）列為 resolved blocker，但那不是真依賴。解鎖方式：請 Leo 先把 VP-16164 Prisma model commit + merge（DB DDL 已於 5/27 上 prod/staging），本 ticket rebase 其上即可從 Dev Blocked 解除；無法等待時退而採方案 A（只 AC1/AC2 不依賴 VP-16164）先交。

**VP-16172** ([BE] Practice Admin Role Enforcement & Integration Request Flow Update)
  - 名目 blocker VP-16164（Blocks）的 DB 層已於 5/27 完成（schema + backfill 落 prod/staging，100% 驗證），Automation 留言也標 VP-16163/VP-16468 resolved，故 schema 依賴已解除。真正殘留 blocker：VP-16164 的三個 Prisma model 尚未進 codebase（本 branch grep 不到 model、無對應 migration），AC2-6 無 generated client 可寫。解封：先把三表 model 補進 schema.prisma + prisma generate（與 Leo 確認在哪個 branch commit）；AC1（RBAC）不依賴新表，可立即啟動。

**LBS-1541** (EMR add free add on (Total Immunoglobulins))
  - 缺 ground-truth ID 與規則來源，PM 未回。解 block 方式（draft Jira comment 給 Leo，勿直接 post）：(1) 取得 ~20 個 trigger package 的明確 package/test ID（或確認可由我對 PackagePrice.name 反查並回 PM 核對，注意 uniqueemrcode 非顯示名稱無法 by-name 查）；(2) 取得 'Total Immunoglobulins' 的 package/test ID；(3) 確認 VA portal 在哪個 repo、是 server-side 還是前端規則（決定 Approach A vs C）。三者任一缺都無法安全實作。

**VP-16784** ([BE] Migrate SHIPPING_RPC to cloud interface)
  - Parent VP-16685 為 Dev Blocked，本 Story 為 Dev To Do。實質 blocker：(a) SHIPPING_RPC_CLOUD 正式 endpoint (lis-shipping-service-grpc.shipping.svc.cluster.local:63142) 由 Xiaoye Li 提供且尚未填進 AKS ConfigMap；(b) cluster-internal DNS 從外部 NXDOMAIN，須等 Trans/EMR 真的部署在同 AKS cluster 內才能實際切流量。Unblock：code 層 fallback wiring 現在就可做且可逆 deploy（走 fallback 等同現狀），真正『切到 cloud』要等 endpoint 進 ConfigMap + in-cluster 部署就緒 + proto byte-compare 通過。

**VP-16685** ([BE] Migration - Replace on-prem dependencies with cloud interfaces in Trans V2 Calendar & EMR)
  - Dev Blocked because cloud URLs/POC for SHIPPING/AUDIT/DASHBOARD/ISSUE RPCs were missing. Now unblocked: PM (Kristine, 2026-05-28) provided URLs by splitting into VP-16784-87 (each Dev To Do). Unblock action: open PR for the completed Calendar body to stage_test and transition the 4 remaining RPCs into their sibling tickets; confirm the AC2 'fully remove on-prem' vs fallback design conflict with PM.

**VP-16164** ([BE] Practice-Level Integration Data Model & Migration)
  - Blocker 不在本票 schema（DB 已完成並 100% 驗證），而在下游 cutover 協調：(a) read-path cutover 依賴 VP-16168 New Provider Detection（自身 Dev Blocked）；(b) MSH6 cutover 需與各 EMR vendor 對齊改動時程——Kristine 正在組 vendor 清單、等 Data Team 提供 Sales info；(c) report_option 6 practice/13 provider CLASSIC vs PERSONALIZED 差異需 client 溝通，且聯絡人要從 CRM 取（ehr_integrations 沒有）；7 個 mixed 待 Sales 決定。解除方式：回 Jira automation 的 blocker-details 問題，明說 schema+migration+backfill 已完成不在 blocker path，本票可推進到「對齊 committed artifact 到 v2 + merge」收尾，剩餘 read-path 歸 VP-16168、MSH6/report_option/ordering 歸 VP-16793/16794/16795 與 vendor/client 協調；建議把本票從 Dev Blocked 移回可推進狀態。

**VP-16759** (Fix getTimeline API on staging - 403 error)
  - Dev Blocked: ticket body is only "getTimeline returns 403" plus a video link; no request URL, query payload, or repro token. Leo already requested these on 2026-05-29 (@Kristine) and no reply. Unblock by obtaining from FE/QA: (1) full staging request URL (which domain/path, confirming v1 vs v2 route), (2) query params/payload, (3) a token that reproduces the 403. With those, curl -i staging in minutes to localize the failing layer (NestJS vs ingress/Cloudflare).

**VP-16166** ([BE] Quarantine Data Model & Service)
  - Blocked 主因是排序而非技術。Leo 自己 2026-05-11 在本票 comment：「應先把 prod HL7 traffic 切到 lis-backend-emr-v2 再做，否則要做兩次」，Kristine 同意「等所有 migration 完成後再排」。因此本票排在 cloud cutover（VP-16685 / VP-16784-87 系列）之後。解 block 方式：(1) 向 Leo/Kristine 確認 cutover 時程；(2) 詢問是否可現在先解 block 開做「純資料表 + service + cron」這段（不接 read path），因為這段不依賴 cutover、與 VP-16164 dual-schema 影子策略一致，可零風險獨立交付，cutover 完成後再接 hook。父 epic VP-16163 本身也是 Dev Blocked。

**QH-3752** (Create API for result sending)
  - Not technically dev-blocked. It sits in To Do only because the dev story (VIB-1641) is Done and the QA mirror has not been scheduled. The real soft-blocker is the empty description / missing AC — confirm with PM whether the deliverable is QA verification + docs (most likely) or there is an uncovered requirement, before doing any work.

**QH-1130** ([BE] Transv2 Rewrite/Document/Test - Utility module (QA mirror of VP-13906))
  - QH-1130 本身狀態 To Do、未被 block。但其『tests』來源 VP-13906 的母 epic VP-13757「Transv2 Batch 2」是 Dev Blocked（QH-1130 無 parent，blocker 不在 QH-1130 層）。最可能原因：Batch 2 其他非-utility sibling 卡住，或在等 QA 簽核。解法：向 PM 確認 VP-13757 的實際 block 點，確認 QA 簽核 utility 是否就是解 block 的前置；不要假設是 utility code 問題。

**QH-2648** (Transfer calendar api for provider to clinician)
  - 未標 Blocked，但實質卡在需求空白：QA Task 與 source Story VP-15115 description 皆空，無 acceptance criteria 或測試案例，無法定義「完成」。解法：向 PM/QA 取得本 ticket 的具體驗收清單（要單測覆蓋、staging E2E、還是 endpoint 文件），再依 Step 4 暫停確認後動工。

**QH-918** ([BE] Transv2 Rewrite/Document/Test - Dashboard Module)
  - QH-918 本身可獨立進行（dev 已 Done/merged，補 unit test 不被父 epic VP-13757 Dev Blocked 卡住）。唯一潛在 blocker 是若選 e2e 路線：staging getTimeline 卡 VP-16759（403），且 VP-16759 自身為 Dev Blocked（等 Kristine 提供 API/payload/token repro）。解法：本 ticket 僅交付 unit test，e2e 待 VP-16759 解除後另補/另開 ticket。

**QH-1860** ([BE] Get Familiar with EMR)
  - 非技術 blocked，是需求 blocked／內容空：description 只有一行 auto-created smartlink、無 AC、無 subtask、source VP-14383 已 Done。Unblock 方式：跟 Leo/PM 確認三件事 — (1) QH-1860 是否就是 VP-14383 已 Done 的 QA 鏡射形式票、可否直接標 Done/Won't Do；(2) 若仍要交付物，期望形式（Confluence onboarding 頁／repo 內 doc／口頭 review）與完成標準（AC）為何；(3) 是否有 QA 流程把此票綁為交接 gate、不可擅自關。確認後即可決定關票或定義最小交付。

**QH-686** (Add more endpoints to provide)
  - 非技術 dev blocked，而是 scope-ambiguous：QA Task 無自身 AC，description 只有 auto-create 引用。Unblock = 向 PM 確認交付型態（手動驗證 vs 自動化 e2e vs endpoint 文件），以及是否有第 4 個未列出的 endpoint。技術上三 endpoint 已上線可立即驗證。

**QH-1104** ([BE] Add Sample Timeline shipping statuses user-friendly labels)
  - 非 Dev Blocked。狀態 To Do 只是 QA 鏡像單尚無人執行驗證。Unblock = 取得可觸發 4 個 shipping 狀態的 staging accession + Kristine 的 Slack 影片/PRD 步驟，排 QA 時段在 staging 實測；注意 VP-16759 getTimeline 403 可能需先解決才能驗。

## 需 PM/Vendor 確認的問題（彙整，可直接拿去問）

**LBS-1547** — Update Clinical Consultation Email Address
  - Zendesk request 2605196651 的 requester 是哪位 clinician（全名 / clinic / 舊 email），最好提供其 LIS 內部 customer_id（=calendar_owner_id），以便在 practice 150105 唯一定位 calendar row？
  - 若以姓名/舊 email 反查命中多筆 Caroline，要改哪一筆 calendar_id？
  - scope 是否僅改 v2_calendar.calendar_owner_email 一個欄位，不需同步更新任何 EMR / patient-portal / 其他系統的 email 設定？
  - 是否需要處理舊 email 已排程但未寄出的 reminder（reminder 以 email 為 recipientKey），或只改 row 即可？

**VP-16832** — [BE] EMR — Auto-Swap GZ to GZ-NY & Trigger Email
  - GZ 與 GZ-NY 在 pricing API 的確切 uniqueemrcode 為何？GZ-NY 是否已 seed 並含 +$80 NY processing fee（影響是否需主動寫 fee）？是否可改由 upstream 處理讓 customer 自行確認是否 NY？
  - 'beta tag' 是否指 repo 既有的 per-clinic beta_programs（jwt-payload / FetchCustomerBetaProgramsForClinic RPC）？gating 意圖是 gradual rollout to specific clinics、per-customer opt-in $80 fee，還是純 kill switch？
  - gz-ny-emr-swap-provider 的 Postmark numeric TemplateId 為何？emr-v2 應自接 Postmark、共用 VP-16169 Dual Notification 基建、還是擴充既有 Vibrant /ehrEmailSupportForProvider 端點？
  - patient state 應以 PID.11.4 直接判定還是先打 patient/address gRPC 驗證？first-time patient（系統尚無記錄）時的預期 swap 行為為何？
  - 'ordering provider' email 來源是 integration 的 contact_email，還是 ORC.12 NPI provider 本人 email？（HL7 OBR/ORC 不直接帶 email）
  - P0-19 與 P0-22 是哪兩張 acceptance ticket（QH-5798 內？）
  - 請提供 PH-789 §6 / §7.3 的 PRD 連結

**VP-16516** — [BE] Meeting Type-Scoped Availability (Weekly Hours & Date Overrides)
  - Epic「clinic/practice-level → per-provider meeting type + 各自 availability」大方向是否確定？舊 v2_practice_event_type + 既有 public booking(Practice→Provider) 是否並存不動（VP-16512 已假設並存）？這直接決定 slot 引擎要不要動。
  - 是否同意分期：先交 Part 1（meeting-type availability 管理 + apply-default，零 prod 風險、不碰共用 booking 引擎），Part 2（slot 引擎接 optional meeting_type_id）待大方向確認後做？Part 1 上線時 FE 暫時還看不到依 meeting type 的 slot。
  - AC3「date-specific 覆蓋 weekly」精確語意：is_unavailable=false + 自訂時段，是『取代當天 weekly 時段』還是『在 weekly 上加回時段』？現有 provider 合併邏輯對 available exception 是 additive，若 PM 要的是 replace 需另寫；is_unavailable=true 整天清空可直接複用既有 full-day-unavailable 行為。
  - apply-default 是一次性複製 provider 當下班表的 snapshot（之後 provider 改班表不連動），還是要 live 連動？且對已有 availability 的 meeting type 是覆蓋還是合併（預設一次性 snapshot + 覆蓋）？

**QH-919** — [BE] Transv2 Rewrite/Document/Test - Utility module 1st Batch
  - 「1st Batch」確切範圍：36 個 utility endpoint 中哪幾個算第一批？（建議我先涵蓋線上高頻：createPatient / updatePatientInfo / updateCustomerProfileV4 / refreshToken / updateCollectionStatus / critical-readout CRUD，若 PM 有指定清單則調整）
  - 「refactor」期待深度：考量父 epic 已 Dev Blocked + 這些是 portal 線上流量，本批是否同意只做『補測試 + 文件，code 不動』，重構留待後批？（我預設採此，若不同意可調整）
  - 文件交付物形式：repo 內 docs/*.md，還是寫到 Confluence pageId 1602355225『back log for transv2』（VP-13757 description 指向處）？

**VP-16885** — [BE] Support EHR enrollment flag on invite
  - Designer note (5/11, Wen Lu+Chris: checkbox always-display) 是否推翻 PRD 的『submit API unchanged / enrollment out-of-scope』那行？以哪個為準？
  - 欄位名定 enrollToEHR？enrollment 行為要 sync（invite response 帶 enrollment 結果）還是 async（fire-and-forget，狀態之後 portal 查）？我預設 async + try/catch（最符合 AC3）。
  - enrollToEHR=true 但沒提供 NPI 時怎麼處理：reject / 存 flag 不 enroll / 警告？我預設『存 flag、不建 membership、回 warning』，不擋 invite。
  - Phase 1 (dev start 6/22) 是否接受『只收+持久化 flag、enrollment 串接做為同 epic follow-up』的最小切片？還是 6/22 就要做完 AC1-4？我預設想一次做完 AC1-4（DB 已 live，不需等別票）。
  - enroll 目標是 practice-level 還是 provider-level membership？invite 當下 provider 無 customer_id，是否走 provisional_providers (VP-16168) 路徑，或以 npi-only membership 暫存後續 reconcile？

**VP-16514** — [BE] Meeting Type Status Toggle & Reorder Endpoints
  - AC2/AC3「reflected in public-facing queries」的 public booking 反映（inactive 排除 + 依 display_order 排序）歸屬哪張？我查過 VP-16516 全文，它只講 per-meeting-type weekly hours/date overrides，ACs 不含 public booking，並非承接者。建議：本張只交付 provider 端 toggle/reorder（已完成），public 反映新開一張 subtask 等 public booking 整體切到 v2_meeting_type 時一起做。是否同意？
  - public booking 目前整條（getAppointmentTypes/availability）仍綁舊表 v2_practice_event_type。是否確認本張不要單獨加一個查新表的 public endpoint（半套無實益）？
  - AC4 字面是『Only owning provider』，但現行 code 放寬為 owning provider 或同 practice 的 clinicadmin 也能 toggle/reorder。是否接受此放寬？（與既有 meeting-type CRUD 授權一致）
  - 本張要與 VP-16513 同 PR #485 一起驗收，還是拆成獨立 PR？
  - reorder 是否總是傳入該 provider 的完整 meeting type 清單？若允許部分清單，未送的 type display_order 不變可能造成排序碰撞——需定義預期行為。

**QH-5840** — Fix ehr integration API CORS error
  - QH-5840 既然 tests 一個已 Done 的 VP-16878，是否就是純 QA 驗收？還是 QA 在 prod/staging 仍重現了新的 CORS error？
  - 若仍出錯：失敗的前端 origin domain 具體是哪個（VI / portal.vibrant-wellness.com / www.vibrant-america.com / 其他）？打的是哪條 URL，走 K8s ingress（api.vibrantamerica.com/api/v1/emr）還是外部 www.vibrant-america.com/lisapi gateway？— 這決定要不要動 ingress 以及動哪一層
  - QH-5409（EMR API CORS in local env，目前 To Do）與 QH-5840 高度重疊，是否可合併或一併驗收？

**VP-16513** — [BE] Meeting Type CRUD API Endpoints - Provider-level meeting types
  - booking_url 網域以哪個為準：BE 目前產 mypatienthubs.com (public-booking.service.ts:191)，但 FE 端可能預期 healmeet.com。FE 接上前需統一，否則連結對不齊。我 default 維持 mypatienthubs.com（與既有 public booking 一致），若要改請告知。
  - slug 在 meeting type rename 時刻意不重產（保連結穩定）、且 update DTO 無 slug 欄（不允許手動編 slug）。PRD 未明寫 — 確認符合預期？我 default 採『rename 不動 slug、不可手動編』。
  - soft-deleted meeting type 的 slug 是否該釋放給同名新建使用？目前 dedup 不排除 is_deleted，重建同名會拿 -2。我 default 維持現狀（slug 永久佔用、保守安全），若 PM 要釋放再改。
  - VP-16514(toggle+reorder) 已實作在同 branch/同 PR #485。要與 VP-16513 同 PR 一起 merge，還是拆兩個 PR 分開 review？

**VP-16169** — [BE] Dual Notification System - Email Triggers
  - Are PRD Template #4/#5/#6 (Postmark IDs 45021853 / 45022272 / 45023981 + staging variants) sent via a NEW Vibrant utility endpoint, or should BE call Postmark directly with a Postmark server token? The existing EhrEmailNotificationService only sends a fixed email_template enum ('reject'|'live'|'requested') and cannot pass a template ID. Default proposal: if direct Postmark, I add a POSTMARK_SERVER_TOKEN env + a thin Postmark client and update both yamls in the same PR.
  - AC7 in-app banner: which DB owns the 'portal notifications' table the banner reads from? emr-v2 schema has no such table. Default proposal: assume it is portal-side (consumed by VP-16170) and emr-v2 only emits the email triggers + an event, unless you confirm emr-v2 must write the record.
  - Idempotency columns notified_practice_at / notified_internal_at (AC6) -- will VP-16168 add them to provisional_providers, or should VP-16169 own that migration? Default proposal: VP-16168 owns them; I coordinate and only add a migration here if 16168 omits them.
  - Do you accept phased delivery (Method B): ship the reusable send methods + practice-admin resolver + audit logging + @Cron reminder skeleton now, and wire Trigger A/B call-sites once VP-16168/VP-16164 merge? Default proposal: yes, proceed with Method B.
  - Trigger C '3 business days' -- which holiday/business-day calendar should the reminder use (weekends only, or a US holiday calendar)? Default proposal: exclude weekends only unless you specify a holiday source.

**VP-16168** — [BE] New Provider Detection Engine & Provisional Provider Records
  - VP-16164 merge 順序：請 Leo 先把 VP-16164 Prisma model merge 進 stage_test，本 ticket base 在其上嗎？（default：是，否則本 branch 無 model）
  - provisional_providers 確切 schema：PRD pageId 2316173315 是否定義了欄位？（default：用上述欄位集，FK 指 practice_integration_id；notified_* 欄位列 optional）
  - AUTO_ENROLLED membership 的 provider_id（HL7 無 customer_id）填什麼？（default：暫填 NPI 或留空待 GetCustomer 回填，需確認 membership 是否允許 provider_id 暫缺）
  - AC1 quarantine：VP-16166 未 ship，本 ticket 只做 detection + 標記/log、真正 quarantine 接線留 VP-16166 可接受嗎？（default：是）
  - AC2 去重粒度：(npi, practice_integration_id) 還是 (npi, practice_id)？一 practice 多 vendor 時希望各自一筆還是合一？（default：practice_integration_id 粒度）

**VP-16172** — [BE] Practice Admin Role Enforcement & Integration Request Flow Update
  - VP-16164 的三個 Prisma model（practice_integrations/provider_integration_memberships/vendor_provider_fields）要在哪個 branch commit 進 schema.prisma？需確認以免我重補一版與你衝突（VP-16164 是 raw-SQL 落地、model 未進 codebase）
  - RBAC（AC1）上線後既有非-clinicadmin provider 對 integration settings 的寫操作會被 403 — FE（VP-16170）/ token 是否已帶 clinicadmin？rollout 順序為何？是否需 feature flag 或先只擋部分端點以免誤擋 prod？預設我採方案 A（AC1 先交）
  - getCustomer 回的 clinic 不含 user 的 target clinic、或 rpc 失敗時：我預設 fail-closed（403），請確認（RBAC 場景覆寫 ticket-routing 的 graceful fallback 通則）
  - 採方案 A（AC1 先獨立交付）還是 B（補 model 後一次做 AC1-6）？預設 A，對齊你 thinnest-slice 偏好

**LBS-1541** — EMR add free add on (Total Immunoglobulins)
  - 請提供約 20 個 trigger package 的明確 package/test ID（package 名稱與 uniqueemrcode 不同，無法靠名稱安全反查；我可先用 PackagePrice.name match 出候選清單回你核對）
  - 'Total Immunoglobulins' 的 package/test ID 是哪一個？
  - VA portal 的這段自動加 add-on 邏輯在哪個 repo？是 server-side（上游 Order/BestDeal API）還是前端 hardcode？此決定我們是 mirror 進 emr-v2（A）還是推給上游（C）
  - Scope：所有 EMR vendor 的 order 都套用，還是限特定 vendor/customer？是否需要 customer/clinic opt-out？
  - Dedupe：若 HL7 order 已含 Total Ig，是否 skip 自動加？
  - Total Ig 加入後，lab processing fee 應排除這個 $0 item（不送進 getLabProcessingFee）還是上游已正確處理 $0？VA 端是如何提交的？
  - 結果層面：Total Ig 的 result 是否要回送 EMR 的 result HL7，還是只做 lab、不回傳？

**VP-15279** — [BE] Implement Order Attribution for Delegated Actions
  - VP-15279 的驗收邊界是否就是『coreSamples delegation table + RPC CRUD』？description 的 AC1/AC2/AC5/AC6（orders 加 ordering_provider_id+entered_by_user_id、order display、audit trail）是否移到另一張下單路徑票？需要我幫忙改 AC 嗎？（我預設：是，本票收斂為 RPC CRUD，QH-3183 的測項一併縮窄）
  - portal delegate 下單的 order 實際寫入點在哪個 repo/service？emr-v2 是 HL7 inbound 不適用，需定位真正 portal order 寫入處才能決定 entered_by_user_id/acting_provider_id 落哪一張票哪個 repo。（我預設：不在本票、不在 emr-v2）
  - VP-15311 [FE] 已 Resolved，FE 實際消費的後端是哪些 RPC？是直接打 coreSamples DelegationService 還是經 transformer-v2 包一層？這決定 transformer-v2 是否需要補 GraphQL/REST resolver。
  - 是否要在本 epic 範圍順手補 transformer-v2 RPC client 接線 + role.service.ts:269-271/334-336 兩個 DELEGATE TODO（選項C，不動 schema）？還是這歸 VP-15274 role API 票？（我預設：建議納入，因為這是讓 delegation 真正寫入的唯一缺口）

**VP-16787** — [BE] Migrate AUDIT_RPC to cloud interface
  - AC2『on-prem reference fully removed』語意：保留 on-prem client 作 fallback backup（對齊 VP-16685、prod 安全）是否可接受？還是要徹底刪除 on-prem client/字串（轉方案 A）？建議 default = 保留 fallback + 僅刪除未使用的 trans/* @Client(audit) 宣告與硬編 IP。
  - cloud endpoint 是否分 st / prod？description 只給一個 …:30113 (default namespace cluster-internal DNS)。st cluster 是否已部署同名 lis-auditlog-grpc-service？若無，AC3 cloud-env regression 無法驗，需 PM/DevOps 提供 st 專屬 endpoint 或確認共用。
  - cloud audit service 是否與 on-prem 讀寫同一資料源？SearchAuditLog/RecordAuditLog 契約（欄位、分頁、無 timestamp filter 的 over-fetch 行為）是否與 on-prem 完全一致？影響 rbac/practice query parity。
  - 本批 4 張 sibling ticket (AUDIT/SHIPPING/ISSUE/DASHBOARD) 的 config-yaml 變更是否合併一個 PR？避免重複漏注入。

**VP-16786** — [BE] Migrate DASHBOARD_RPC to cloud interface
  - AC2「fully removed on-prem reference (192.168.60.6:31987)」是字面要求嗎？該 IP 其實整個 repo 已不存在，且 prod config 的 DASHBOARD_RPC 已指 cloud。我傾向比照 sibling (customer/clinic, VP-16685) 保留 cloud-primary + on-prem fallback——請確認可接受 fallback 留存（實質達標），還是堅持移除整個 on-prem 路徑（方案 B 硬切）？
  - DASHBOARD_RPC_CLOUD 的 st 環境是否有可達的 dashboard cloud endpoint？目前 yaml/st-env.yml 連 DASHBOARD_RPC 都沒設，st regression 需要一個可連的 dashboard service。
  - 四張 RPC 票 (VP-16784/85/86/87) 同 repo 同 pattern——要合併成單一 PR/branch 一起做，還是逐張獨立 PR？順帶 dashboard.service 內 client3 (Shipping, 屬 16784) 是否一起遷？

**VP-16785** — [BE] Migrate ISSUE_RPC to cloud interface
  - AC2「On-prem reference (192.168.60.6:30071) is fully removed」是字面 hard remove，還是接受 cloud-primary + on-prem-fallback（保留 on-prem 當備援）？我預設採方案 B（fallback，對齊 VP-16685 已驗收 pattern）；若 PM 堅持 hard remove，請先確認 LIS-transformer-v2 prod pod 確定與 issue service 同 cluster、.svc.cluster.local 可解析，否則會 NXDOMAIN 全掛。
  - VP-16784/85/86/87 四張同構 RPC 是否合併同一 PR？我建議 issue（SHA-pinned，風險最低）當 pilot；但 dashboard(:latest mutable) 與 audit(_cloud 分支 build) proto 不可假設同步，若合 PR 這兩張要額外驗 proto。
  - 確認本 ticket 在 LIS-transformer-v2 實作（非 EMR repo），且 cloud DNS 由 transformer-v2 的 ISSUE_RPC_CLOUD ConfigMap key 提供？EMR repo 對此 RPC 無 client code、無需改動。

**VP-16784** — [BE] Migrate SHIPPING_RPC to cloud interface
  - AC2『on-prem reference fully removed』是否接受先保留 on-prem 作 fallback、待 in-cluster 部署 + endpoint byte-compare 驗證後另開 cleanup ticket 移除？（直接移除違反 VP-16685 fallback 鐵律且 endpoint 尚未 ready）
  - SHIPPING_RPC_CLOUD 正式 cloud endpoint 是否已由 Xiaoye Li 填進 AKS ConfigMap？shipping.proto 是否與 on-prem 同步可 byte-compare 驗證？
  - 是否要把 sibling VP-16785/86/87 (ISSUE/DASHBOARD/AUDIT) 併進同一 branch/PR 一起做？（caller 大量重疊同檔，分開改會反覆動同檔；但會模糊各 Story 驗收邊界，且 audit cloud option 尚未建）

**VP-16685** — [BE] Migration - Replace on-prem dependencies with cloud interfaces in Trans V2 Calendar & EMR
  - VP-16784 AC2 says 'fully remove the on-prem 192.168.60.6 reference', but VP-16685 already ships cloud-primary + on-prem fallback. During cutover do we KEEP the fallback safety net (my default: keep — cloud is primary/default, on-prem only on transient failure; reword AC2 to 'no longer connects to on-prem by default, only on transient fallback'), or hard-remove on-prem now?
  - Confirm Event Hub/Redis are out of scope for VP-16685 per Leo's 2026-05-22 comment and the migration stops at gRPC RPC (my default: excluded, documented on ticket, Kafka/Redis untouched).

**VP-16164** — [BE] Practice-Level Integration Data Model & Migration
  - 本票（schema+migration+backfill）是否可與 cutover 協調脫鉤，先把 committed artifact 對齊 v2 live DB 後 merge、解除 Dev Blocked？read-path 切換歸 VP-16168，MSH6/report_option/ordering 歸 VP-16793/16794/16795。（我的 default：脫鉤、先 merge schema 收尾）
  - 新表在 cutover 前要不要先做 dual-write（新 integration request/approve 同時寫新表），避免新表 stale？若要，屬本票還是 VP-16172？（我的 default：拆成 follow-up subtask，不擋本票 schema merge）
  - MSH6 cutover：809 customer 清單已備，何時與各 vendor 對齊改動？此決定 VP-16793 何時動 live DB
  - report_option 6 practice/13 provider 的 CLASSIC vs PERSONALIZED 差異標準化前要不要先 client 溝通？RSM/CAM 聯絡人請從 CRM 提供（ehr_integrations 無此資料）

**VP-16759** — Fix getTimeline API on staging - 403 error
  - Provide the exact staging request that reproduces the 403: full URL, query params, and a valid token (this is the only hard blocker; Leo asked 5/29, still unanswered).
  - Does the FE call hit the v1 (LIS-transformer:3190) or v2 (LIS-transformer-v2:3390) /dashboard/user/timeline on staging? Need the ingress route mapping since both paths are identical.
  - Is the preview origin *.va-portal.pages.dev approved to be accepted by staging? If the 403 is an origin/gateway allowlist decision, PM/security must approve adding it — agent will not widen the allowlist unilaterally.
  - Confirm the 403 response body shape from the video/repro: a NestJS JSON error vs Cloudflare/ingress HTML — this alone tells us whether it is an app or infra issue.

**QH-5409** — EMR api has CORS issue in local env
  - QH-5409 的『local env』repro，FE 打的是 staging.vibrant-america.com（= VP-16627 已知的 gateway host 打錯、nginx 405，非 CORS）還是本機的 emr-v2（localhost:3000）？VP-16627 captured 的 curl 帶 Origin: http://localhost:8080 且打 staging host，若 QA 沒有別的 repro，本單就是同一 case。
  - 既然 parent VP-16627 已 Inactive、sibling VP-16878/QH-5840 已 Done，QH-5409 是否可直接 close？還是 QA 有 VP 沒涵蓋的新重現需要 emr-v2 側處理？

**VP-16166** — [BE] Quarantine Data Model & Service
  - Cutover 時程：prod HL7 切到 lis-backend-emr-v2 何時完成？是否可現在先解 block，開做純資料表/service/cron（不接 read path）部分？（我預設：可獨立先做這段）
  - PRD Open Q1：provider resolve 後 quarantined order 要 auto-reprocess 回 BullMQ 還是 admin 手動點？（影響 status 機轉與是否 hook 回 queue。我預設：先手動，auto-reprocess 切 sub-task）
  - PRD Open Q3：7 天硬過期，還是允許 admin 延長？（影響 cron 設計。我預設：硬過期 7d，延長另排）
  - AC6 dead-letter dual-write 落地：repo intake 用 BullMQ+Redis（process-hl7-file），result 用 Kafka。DLQ 要用 BullMQ failed-job 機制、新建一張 dead_letter 表、還是另一條 queue？（我預設：另建表最簡單可審計，但須你指定）
  - resolution_logs 表是否屬本票範圍？PRD Feature 1 列出但本票 AC 未明列。（我預設：納入，cheap 且 audit 隱含需要）
  - Prisma enum vs String：經查 schema 已有 35 個 enum、VP-16629 後的 EHR-V2 新表都用真 enum，我建議改用真 Prisma enum（與同 epic 一致）；請確認，因 VP-16164 當時記的是 String 慣例。

**QH-3752** — Create API for result sending
  - QH-3752 is the QA mirror of VIB-1641 (already Done) and both descriptions are empty — is the expected work QA verification + API documentation, or is there a VIB-1641-uncovered requirement to build?
  - Which environment for verification — staging/local? And is prod transmit (send_result:true to the real vendor SFTP) permitted, or should I stay on read-only generate-content/patient-hl7-content paths only?
  - Deliverable format: a Jira QA sign-off comment, a docs/ markdown page, or both?

**QH-2577** — Re-push report to EMR 2511046917
  - QH-2577 是真的要再推一次/驗證，還是 VP-15050 已 Done 後殘留的 QA 鏡像可直接關掉？provider 現在 EMR 端是否仍看到 TNP markers？
  - 2511046917 是 accession_id 還是 sample_id？對應哪個 vendor / provider / clinic（決定 SFTP target 與 file size limit）？
  - 上次推舊版的確認根因為何——來源 report 是否確實已重新核可成 marker-removed 版本？（不要預設是 PDF cache 問題，line 1162 不支持該理論）
  - 走 ad-hoc gRPC GenerateResultHl7 script（仿 repush-samples-by-date-range.ts）還是 QH-1775 的 manual push RPC（若已 deploy）？
  - prod pusher pod 的 gRPC endpoint / 連線方式為何（須打 pusher 不能打 intake，POD_ROLE guard）？

**QH-4352** — [BE] Update the supported EMR vendor list in Settings
  - QH-4352 指派給你是要你親自跑驗證並回填 QA 結果，還是只是掛名、實際由 QA 執行？（決定是否有任何工作量）
  - 自 2026-04-21 migration 後 Notion EMR Vendor List 有無新增/變動 vendor？若有，需用 bounded SQL 補設新 vendor 的 is_public（這是唯一可能的真實 code/SQL 工作）。
  - 驗證對象是 staging、prod 還是兩者都要？
  - Admin panel / 報表 是否也消費 GET ehr-vendors endpoint？若是，現行 is_public default 過濾會讓 admin 不帶參數時看不到 private vendor，是否為預期？

**VP-16186** — [BE] Connect to prod db
  - （給 coreSample team / Kristine）prod coreSample 是否已 deploy GetPatientSamplesByTimeRange 的 server 實作？對應 prod gRPC host:port？（決定本 ticket 能否 BE 單方完成；proto 有不代表 server 有）
  - （給 PM）本 ticket 要驗的是哪條路徑：只驗 read-only endpoint POST /result/patient-hl7-content，還是要連 VP-15659 真正的 Agent enrollment pipeline（寫 sandbox patient_xxx/reports/ 檔，AC1-AC6）一起接 prod 驗？字面 'the connection' 偏前者，但 VP-15659 AC 是後者。
  - 用哪個真實 prod patient 驗證？VP-15659 提 testing account 999997 — 仍用它嗎？對應 patient_id 是多少、是否有多筆 lab？
  - 若多 sample patient 驗證確實踩到 95s 慢查詢甚至 gateway timeout，是否要在本 ticket 內處理（timeout/批次/預生成），還是另開效能 ticket？（engineer 預設另開，需 PM 拍板）

**QH-4350** — Fix MSH.5 and update MSH.12 for Charm results
  - 向 Kristine 確認 QH-4350 的驗收標準：是否「抓一筆已實際傳給 Charm 的 result HL7（SFTP + HTTP POST 兩路徑），確認 MSH-5=ChARM_EHR、MSH-12=已選定版本（2.3.1 或 2.5.1）」即可關票，且不需再次 repush（VP-15948 已完成）？
  - 確認 Charm 已正式驗收 VP-16010 的修正（vendor 端 ACK 正常、無因 MSH-12 版本造成 reject），避免我們關票後 vendor 又回報問題。

**QH-3324** — [BE] Remove participant limits for event creation - Clinical
  - QH-3324 是否就是『對 Clinical(practice 150105) 跑 VP-15374 那套 4-AC QA 驗證』即可結案？我預設是（方案 A，0 code change）。
  - 驗收的『只有 Provider，沒有 Patient』在 Clinical 入口具體指哪種？因 createEventByPatient 對 clinician_calendar_id 強制 role==='clinicadmin'（service:1665），一般 provider-only 場景目前會被擋。請確認這是預期行為還是需放寬。
  - 是否需要產出可回歸的自動化測試（補 event.service.spec.ts，目前對 createEventByPatient 0 覆蓋）？還是手動 staging 驗證 + 報告即可？

**QH-1130** — [BE] Transv2 Rewrite/Document/Test - Utility module (QA mirror of VP-13906)
  - QH-1130 是否就是對 VP-13906 已交付 utility REST 的 QA 簽核（補測試/文件、不改 endpoint 行為）？預設我採此 scope。若要我補 code 行為請明說。
  - controller 目前 36 個 endpoint，但 Confluence 2197127170 只記到 29、且 criticalReadoutAuthorizedContacts/createPatient/updatePatientInfo/refreshToken 未文件化也 0 測試 — 這 6 個是『刻意 out-of-scope（之後另開 ticket）』還是『屬本 batch 待補測試/文件』？
  - 母 epic VP-13757『Transv2 Batch 2』Dev Blocked 的實際 block 點是什麼？是 utility 以外的 sibling，還是在等 QA 簽核 utility？
  - QH-919（utility 1st batch，tests VP-13759 仍 Dev To Do）尚未 dev-complete，但 2nd batch 已 Done — 兩者共用 src/utility/。QH-1130 的 QA/測試範圍要不要把 1st batch 一起涵蓋，還是只限 2nd batch 交付的子集？

**QH-2259** — [BE] Clinical Schedule Migration - Import History Schedule Data
  - QH-2259 的預期產出是否就是『對 VP-14750 已遷移資料做 QA read-only 驗證並回報』？（我預設是 read-only，不碰 prod 寫入）
  - 舊 Lab Consult 行事曆 source DB 連線 + 受影響 clinician 名單何處取得？（migration service 直連的舊 DB；這是最可能的阻塞點）
  - 驗證範圍：全部已遷 clinician 100% 比對（我預設此），還是指定子集？
  - 若驗出缺漏，回開新 bug 票補跑（我預設此，不在 QA 票動 prod），還是允許在本票範圍內補 migration？
  - VP-14656 epic 目前是否確認為 Done？（本 pass 未核實其狀態，VP-14750 確認 Done）

**QH-2648** — Transfer calendar api for provider to clinician
  - QH-2648 的具體驗收標準是什麼？VP-15115 與本 ticket description 皆空（僅 auto-create stub）
  - 期待產出是『單元/整合測試覆蓋』、『staging E2E 跑過』、還是『endpoint 文件』？若是文件，是否與 QH-824（Create Doc for updated Endpoint for Calendar）重疊？
  - VP-15115 已 Done 且 prod 被 VP-16410/16499/16520/16521 依賴運作中 — QH-2648 是僅做 QA sign-off 形式關閉，還是真有未驗的行為缺口需重現？
  - by-patient mutation 是否僅限 customer token（PR #216）— 此 token gating 是否屬本 ticket 驗證範圍？

**QH-680** — Add oauth
  - QH-680 的預期交付物是「QA 跑測試驗證並關票」，還是要 BE 出新東西？(票是 QA Task、母票 VP-13527 已 Done，我判斷是前者)
  - 若要我(BE)介入，範圍是「補自動化測試(outlook/zoom e2e)」還是「補/校對 API 文件」？若要，我建議掛到 QH-918/919/1130 而非此票。
  - 需跑完整 oauth consent flow 的話，staging 是否已配好 Google/Microsoft OAuth app 憑證與 redirect URI 白名單？沒有的話我只能做 API-level smoke。

**QH-1591** — Optimize code for Calendar Module
  - 範圍是否限「Phase 1.1 補 index」？我 default 只做這段（理由：來源 VP-14142 是 AI roadmap 非規格，現狀核對後唯一確認真缺、低風險、可量測的就是 index；其餘 phase 多已被 VP-16685 完成或衝突）。若同意請確認，不同意請指定要納入哪些 phase。
  - roadmap 的 cache layer / Repository / CoreModule 重構是否要排？建議獨立開 Story、勿夾在此 P2 QA Task，且須等 VP-16685(cloud migration, 動同一 src/calendar/shared gRPC 層)先 merge 才能動架構。
  - 可否在 calendar_prod 以 CREATE INDEX CONCURRENTLY 執行 index？需確認 maintenance window 與是否接受短暫 IO 升高。
  - 加 v2_meeting_request index 須與 Meeting Type epic(VP-16512/13/14/16)對齊——這幾張是否已規劃 v2_meeting_request 的 index/schema 改動？避免重複。

**QH-918** — [BE] Transv2 Rewrite/Document/Test - Dashboard Module
  - QH-918 的 Done 定義 = 補 unit test + 既有 Swagger 即可，還是必須含打真實 endpoint 的 e2e 驗收？（我預設前者，e2e 另開 ticket）
  - 是否同意 e2e 部分待 VP-16759（getTimeline 403）解除後另開 ticket，QH-918 先以 unit test 收尾？
  - 測試 coverage 有無硬性門檻——5 個 endpoint 全 happy path 即可，還是要含 error/權限分支的覆蓋率百分比？

**QH-2257** — Change Gut Zoomer Results to Classic Complete Report
  - QH-2257 是 VP-14748（已 Done）的 QA 追蹤鏡像。VP-14748 的 report_option 變更已在 1/21 完成，但 1/26 CAM 要求 re-push 的部分在 ticket 上無後續回覆——請確認：當年那批 1/12–1/26 的 Gut Zoomer 報告是否實際 re-push 給 CAM 了？還是只改了設定？
  - 若 re-push 從未完成且 CAM 現在仍需要，請提供明確的 accession_id 清單（當年無法判斷哪些報告含 Gut Zoomer），並確認是否仍要重推 6 個月前的舊報告。
  - QH-2257 本身是否只是 QA 獨立驗收用的鏡像、可在驗證設定無誤後關閉，還是 QA 想要我額外提供驗收證據（如 base-report-service style=advanced 的實際 PDF 輸出）？

**QH-1860** — [BE] Get Familiar with EMR
  - QH-1860 是否就是 VP-14383（已 Done）的 QA 鏡射形式票？可否直接由 Leo 標 Done / Won't Do？
  - 若仍要交付物，期望形式是什麼（Confluence onboarding 頁、repo 內 doc、還是口頭 review 即可）？「familiar」的完成標準（acceptance criteria）是什麼？
  - 是否有任何 QA 流程把這張票綁為 onboarding/交接 gate，因此不能擅自關？

**QH-686** — Add more endpoints to provide
  - QH-686 期待的交付物是『手動驗證並回報結果』，還是要補自動化 e2e 測試 或 GraphQL endpoint 文件？（我預設先做手動 live 驗證，若要 test/doc 請告知）
  - VP-13533 三項已在 stage_test 上線，QH-686 是否就是驗證這三項 (clinic_customers / getCanceledMeetingRequests / getClinicLocations)？有無第 4 個未列出的 endpoint？
  - clinic_customers 目前無 role filter 回 clinic 全部 customer、getCanceledMeetingRequests 只回 future + 'Canceled by patient'，這兩個商業語意是否符合預期？
  - 若要文件，是否與 QH-824（Create Doc for updated Calendar Endpoint）合併以免重工？

**QH-1159** — Update calendar module to use v2
  - QH-1159 的 Done 定義是否 = 7 個有 cloud endpoint 的 RPC byte-parity 通過 + build/start:dev pass + 既有 calendar spec 綠？（我預設：是，純 QA 即可關票。）
  - 4 個無 cloud endpoint 的 RPC（SHIPPING/AUDIT/DASHBOARD/ISSUE）走 on-prem fallback，是否同意列為 QH-1159 已知 gap 並 link VP-16784-87、不阻擋本票？（我預設：是。）
  - 是否要順手補 with-cloud-fallback.util.spec.ts（方案 B），還是嚴守 QA-only 不開 branch？（我預設：先 A，util spec 視你意願。）

**QH-1660** — EHR Order Missing
  - Has Susan Parris's re-placed (non-SZ) order produced results / attached correctly to her Vibrant profile? (default: yes per VP-14195 — if so, close QH-1660)
  - The Sales request 'ensure discontinued tests are not selectable going forward' — should this be a separate ticket tracking Cerbo compendium-code cleanup with the Order team? (default: yes, it is vendor/Order-team scope, NOT lis-backend-emr-v2 and NOT part of QH-1660)

**QH-1775** — Deploy Zichen's new manual push RPC service
  - QH-1775 是否就只是 VP-14295 的 QA 驗收關單？若是，是否同意我用 grpcurl 對 prod 192.168.60.6:31317 做 live 驗收後直接 transition Done（含 comment 記錄 sample_id/record_id/上傳路徑）？
  - 驗收用的目標 sample 用哪個？建議用 QH-2577 的 report 2511046917 當活靶子（可重推、scope 明確）——可以嗎？
  - VP-14295 description 寫的『remove the customers from old table once it's finished』是否屬本 ticket 範圍？因為那是 prod DB DELETE，我會建議拆到 EMR migration umbrella 另立 bounded+verified 操作，不塞進這張 QA ticket，請確認。
  - 本 ticket 是否涉及把這支 RPC 搬上 AKS/cloud 重新部署（呼應 EMR cloud migration）？若是才會改採方案 B 動 deploy manifest。

**VP-9299** — customer email - send result ready - update product list
  - product_list 是否接受改為只列 report_staus=='Final' 的報告 (對齊 codebase 既有 L8223 pattern)？V1 舊行為是不過濾全列；改 Final-only 可能讓清單變短。我預設採 Final-only，若不同意請告知。
  - 此 ticket 只涵蓋 beta 分支 (result_ready_new)，不涉及非 beta 分支 (result_ready，目前完全無 product_list)。我預設不碰非 beta 分支，確認可。
  - (ship 前我自己驗，非問 PM) 用 ticket 提供的 barcode 2410246397 實打 V2 確認 finished_reports element 欄位與 status 取值。

**QH-1104** — [BE] Add Sample Timeline shipping statuses user-friendly labels
  - QH-1104 既然只是 VP-13889 的測試鏡像，是否直接由 QA 在 staging 跑驗證並關單即可？（預設：是，不需再寫 BE code）
  - Sample Timeline 是否要顯示 DELIVERY_EXCEPTION→Delivery Issue？目前 v1 trans.service.ts 的 timeline shippingStatusMap 只涵蓋 4 個狀態、未含 DELIVERY_EXCEPTION——若 AC 要求顯示，這部分疑似未實作，需確認是否屬 VP-13889 範圍或另開單
  - 能否提供可觸發 SAMPLE_SHIPPED_BACK / LAB_RECEIVED 的測試樣本或 staging accession，以完整覆蓋 4 個狀態？
  - staging getTimeline 目前是否仍有 VP-16759 的 403 問題？若有需先排解才能驗證

**QH-862** — Add readiness and liveness Probe to transv2
  - prod probe 早已上線、/health 已存在，本 ticket 真正交付是否就只剩『啟用 staging probe + 修 port』？（我 default：是）
  - 是否需要 deep/dependency-aware health check（檢 DB/Redis/gRPC）？還是 shallow /health 即可？（我 default：shallow 即可，deep 另開 ticket）
  - 是否要拆 liveness 與 readiness 成不同 path（/health/live、/health/ready）？（我 default：維持單一 /health，與 prod 一致）

**QH-824** — Create Doc for updated Endpoint for Calendar
  - QH-824 驗收標準＝『僅 VP-13671 的 3 個 endpoint (getClinic / clinic-location CRUD / getCanceledMeetingRequests) 文件存在且正確』即可 close 嗎?還是要連同後續 ticket (VP-16513/16514/16516 meeting-type) 新增的 calendar endpoint 一起補成最新完整 doc? (界定 A vs B-broad 邊界)
  - 文件 reviewer @Jiaming Ma 是否已在 VP-13671 sign-off?若已,QH-824 可直接引用其 review 作為 QA 通過依據;這也決定我修正 clinic_customers 描述後是否需再請其 re-review。

**QH-610** — Update data format for questionnaire
  - QH-610 是否就是『驗證 VP-13464 已上的 questionnaire 格式』的 QA 收尾？還是有未寫進 ticket 的新一輪格式調整需求？（description 全空，無法判斷意圖）
  - cardio_genetics_questionnaire 是否屬於應支援的 questionnaire 類型？若是：backend required-map 是否已回 has_cardio_genetics_questionnaire flag、對應 inventory status endpoint 是哪個、以及正確的 questionnaire URL（目前複製 cardioZoomerPage）為何？若否：是否同意刪除這段 dead mapping？
  - 驗證的 acceptance criteria 是什麼？要驗哪些 questionnaire 類型 / sample，是否有指定測試資料？

**QH-211** — Create Doc for CheckSampleAttributes and BatchCheckSampleAttributes
  - 文件落點:沿用 QH-824 Calendar doc 的 Confluence space/parent page 嗎?(我預設 yes,Confluence structured markdown)
  - BatchCheckSampleAttributes 的 deprecated no-op 事實要一起寫進文件嗎?(我預設要寫,以免整合方誤用)
  - 要附 grpcurl 範例 payload 嗎?(我預設附)
  - 三個 RPC 全寫還是只寫標題的兩個?(我預設三個,因 New 版才是實際使用版本)

## 建議處理順序（綜合 priority / effort / blocker / 依賴）

**1. 可立即動的 quick wins（S、無 block、無需 PM）**：VP-16512, QH-4608

**2. 先發 PM 問題、答了即可做**：QH-5840, VP-16513, VP-15279, VP-16787, VP-16786, VP-16785, QH-5409, QH-2577, QH-4352, VP-16186, QH-4350, QH-3324, QH-2259, QH-680, QH-1591, QH-2257, QH-1159, QH-1660, QH-1775, VP-9299, QH-862, QH-824, QH-610, QH-211

**3. Dev Blocked，需先解 prerequisite/依賴**：LBS-1547, VP-16832, VP-16516, QH-919, VP-16885, VP-16514, VP-16169, VP-16168, VP-16172, LBS-1541, VP-16784, VP-16685, VP-16164, VP-16759, VP-16166, QH-3752, QH-1130, QH-2648, QH-918, QH-1860, QH-686, QH-1104

**4. 大工程（L/XL），需排期 + 可能拆 story**：VP-16832, VP-16516, VP-16169, VP-16168, VP-16172, VP-16787