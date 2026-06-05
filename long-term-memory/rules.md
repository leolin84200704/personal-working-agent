---
id: rules
type: ltm
category: pm_patterns
status: active
score: 0.1544
base_weight: 0.8
urgency: 3
created: 2026-05-20
updated: 2026-05-20
links:
- INCIDENT-20260518
- LBS-1487
- VP-15460
- VP-16165
- VP-16245
- VP-16280
- VP-16329
- VP-16337
- VP-16361
- VP-16391
- VP-16396
- VP-16410
- VP-16416
- VP-16474
- VP-16476
- VP-16502
- VP-16612
- VP-16617
- VP-16629
- VP-16664
- ticket-routing
tags:
- rules
- constitution
- feedback
- auto-generated
summary: Auto-aggregated constitution from 34 rule-bearing paragraphs across STM
---




# Rules / Constitution

> 自動萃取自所有 STM 的 `## User Feedback` / `## Lessons Learned` / `## Decisions Made`
> 段落中含 imperative 語氣或 Leo 明確指令的句子。
> 由 `scripts/extract-rules.py` 維護，下次 run 會覆蓋。
> Last updated: 2026-05-20 — total 34 rules across 8 categories

## Categories

- [Scope / requirement / PM communication](#scope-comm) — 11 rules
- [Git / branch / commit / push](#git-workflow) — 7 rules
- [Other / uncategorized](#other) — 4 rules
- [Error handling / throw / log / silent](#error-style) — 4 rules
- [Production safety / kafka / email / SFTP](#prod-safety) — 3 rules
- [Review flow / report format / approval](#review-flow) — 2 rules
- [Testing / mock / verify](#test-style) — 2 rules
- [DB / SQL / FK vs derived column](#db-style) — 1 rules

---

## Scope / requirement / PM communication <a id='scope-comm'></a>

### [[INCIDENT-20260518]] · _User Feedback_

### [2026-05-18] Leo 觀察到 sample 2552289 manual retry 就 OK
→ 證實上游錯誤 transient，emr-v2 應該 retry。改 retry 條件擴大到 UNAVAILABLE/UNKNOWN/INTERNAL（43dea1b）。

### [[VP-16245]] · _Lessons Learned_

### [2026-05-04] — Folder path /acw rollback
- **PM 轉述 vendor 回覆的縮寫要 sanity-check** — Kristine 4/28 留言「Cerbo confirmed that we should use /acw」，但 Alpine Wellness Clinic 縮寫應該是 AWC 不是 ACW。當時照單全收沒質疑，導致 prod DB 設成 /acw 5 天。Leo 5/4 親自查 SFTP server 確認實際是 /awc。應該 pattern：縮寫不對應 practice 名稱時主動 push back PM 再次跟 vendor 確認。
- **/acw 5 天無流量是運氣不是 process** — 4/29~5/4 hl7_file_input、result_transmission_records、result_records 對 clinic 11372 都 0 筆，因此沒造成資料漏失。但這是低流量診所的偶然，不能事後合理化「path 改錯沒事」。
- **Path-only rollback 流程**：5 條 UPDATE（ehr_integrations × 2 三條 path、order_clients × 2 remote_folder_path、sftp_folder_mapping × 1 server_folder）single transaction + pre-check sanity guard + 驗證 target path 不在 sftp_folder_mapping 既有（避免 unique constraint）。status 不變 → 不寫 ehr_integration_status_history。

### [[VP-16391]] · _User Feedback_

### [2026-04-30]
- Leo 要求：先分析、不用做（Step 2-3, 不進 Step 5）
- 方案選擇歷程：先選 B → 看 DB 設計細節後改選 C + 設計 2
- Lab consult filter: 「不需要 [practice_event_type]，if and only if v2_event.clinic_id = 150105」（實際欄位 `v2_event.practice_id = 150105`）
- Postmark template ID 33802989: prod/staging 先共用同 ID
- Postmark template variables 已提供完整 7 個欄位
- 「請詳細測試過」— 進 Step 5 後要寫 unit test 並 npm test 全綠

### [[VP-16416]] · _Lessons Learned_

1. **AC 字面「no silent fallback」≠ 一定要 throw**：PM 寫 AC 時通常希望「不要 silent」即可，warn log + 沿用既有 fallback path 也算 graceful。先給 default 解讀讓 PM 推翻，比預設 strict 解讀少一輪 review。

### [[VP-16476]] · _Lessons Learned_

### [2026-05-06 11:40] 流程
- **LTM「規則表」要 cross-check code source**：LTM 是 cached 結論，可能寫錯（VP-16423 釐清表就錯了）。引用 LTM 規則表前先 grep 對應程式碼確認；發現有錯時當下修正 LTM。
- **PM ticket + 整理性質改動混合**：Leo 看到資料品質問題時可能順手提「全表整理」，agent 要主動 surface「PM 原 request 還在嗎」+ 同步呈報兩件事的數字。
- **Apply prod 不可逆改動前必跑 dry-run + 顯示數字**：即使 Leo 說「直接做」，呈報 dry-run 結果（多少 row 變化、target row 預期狀態）+ pre-check sanity guard 是 Safety First 必要程序。

### [[VP-16612]] · _User Feedback_

### [2026-05-18]
- "clinic_id = 150105 and role === 'clinicadmin'" — Leo narrowed my proposed filter from "provider only" to "exclude this exact group, keep everything else". **Important pattern**: PM's natural-language exclusion ("not Clinical Team") is more precise than my proposed inclusion ("only providers"). Narrower exclusion preserves edge-case behavior (patient role, external clinicadmin) without over-reaching.
- "只是 48 hr, 24 hr, 15 min 的 reminder 拿掉" — explicit scope ring-fence: only reminder dispatcher, NOT create-email flow.
- "ok 收尾，都沒問題就是等 merge" — Leo committed himself (commit 69cdb8a authored by leolin84200704@gmail.com personal email), expects me to do retrospective + memory distill + stop.

### [[VP-16612]] · _Decisions Made_

### [2026-05-18]
- Filter location: `dispatchEventReminder()` line 110.
- Spec literal: exclude `practice_id=150105 AND role='clinicadmin'`. Don't touch create-email flow (separate scope).
- Touch `clinicianParticipant` find (line 115) — NO. Stays as `role === 'clinicadmin'` without practice_id restriction; out of ticket scope.
- Schema/migration: none. `v2_calendar.practice_id` already exists.
- Spec test scope: 4 new test cases; update fixture to add `practice_id`; rewrite tests previously asserting "all participants receive".

### [[VP-16617]] · _Lessons Learned_

### [2026-05-14]
1. **When LTM has two statements that should agree, treat them as a yellow flag — verify against authoritative source before acting**. Internal LTM contradictions are silent traps; the older entry might be the wrong one.
2. **`COUNT(DISTINCT col)` in SQL silently ignores NULL** — use JS Set semantics or `COUNT(DISTINCT COALESCE(col, '__NULL__'))` if NULL should count as a distinct value. (Recorded in patterns.md.)
3. **Scope creep is fine when the invariant the user surfaces is a real one** — but flag it explicitly ("this is now bigger than the ticket") so timeline expectations match. VP-16617 ballooned from 1 finalize to 845+92+296 row audit without scope re-confirmation.
4. **Dead vendors are still in the dataset and bias audit numbers** — 91/92 of the kit_delivery misalignments were PF (dead per VP-16463), 84/87 of the dup combos were PF. Always check "is this fix vacuously cleaning dead data?" before claiming impact.
5. **`kit_delivery_option` ↔ `kits_options` mapping pinned to ParseHL7.java line 930**: `0↔NON_BLOOD_ONLY`, `1↔BOTH_BLOOD_AND_NON_BLOOD`, `2↔NO_DELIVERY`. Any future stub finalize defaults to `NON_BLOOD_ONLY + kits=0` (most common pattern, ~73% of LIVE aligned rows).
6. **Scope discipline — prod-wide audit findings belong to umbrella migration scope, not the single integration ticket that surfaced them.** VP-16617 finalize completed Elation Harris LIVE successfully (that IS the ticket). The 366 remaining rows + schema drift + PF dead-vendor cleanup are EMR-Backend → lis-backend-emr-v2 migration follow-ups. Closing VP-16617 done; CSV `/tmp/emr-backend-migration-followups.csv` moves to migration tracking, not posted to VP-16617.

### [[VP-16629]] · _User Feedback_

### 實作（branch: feature/leo/VP-16629）
新增：
- `prisma/schema.prisma`: 加 `EhrVendorSftpTemplate` model
- `prisma/migrations/20260519_add_ehr_vendor_sftp_template/migration.sql`: CREATE TABLE
- `scripts/seed-ehr-vendor-sftp-templates.ts`: ts-node seed（dry-run 支援）
  - 從 ehr_integrations 取每 vendor latest record
  - Cerbo 用 regex `^/([^/]+)/(orders|results)/?$` 反推 folder → `{folder}` placeholder
  - local paths 從 sftp_folder_mapping 用 emrName match
  - sftp_source_id 從 emr_sftp_source 用 emrName match
- DTOs: `approve-integration-request.dto.ts` / `reject-integration-request.dto.ts`
- `TechnicalRequirementsDto` 加 `folder` (Cerbo required, regex `^[a-zA-Z0-9_-]+$`, 1-100) + `reportOption` (number 1|2)

### [[VP-16629]] · _User Feedback_

### [2026-05-19] Leo 要求寫詳細 doc + 確認 create request field gap
- Doc 寫到 `lis-backend-emr-v2/docs/vp-16629-approve-reject-api.md`
- Leo 列 5 個欄位質疑「create request 沒 collect」：`msh06_receiving_facility / legacy_emr_service / sftp_result_path / sftp_ordering_path / report_option`
- 我的調查結果：
  - `msh06_receiving_facility` → ✅ 已 collect（在 nested `technicalRequirements.msh06ReceivingFacility`，line 121 of integration-request.service.ts 寫入）— Leo 可能誤記
  - `legacy_emr_service` → ❌ 未 collect。result pipeline 用作 MSH-5 + emr_service identifier，fan-out 鍵之一。Fallback chain: `ehr_vendor.code → legacy_emr_service → 'DEFAULT'/'UNKNOWN'`
  - `sftp_result_path` → ❌ 未 collect。result delivery target folder。Fallback: `integration.sftp_result_path → vendor.sftp_result_path → '/results'`（但部分 caller 沒走 vendor fallback，直接退 `/results`）
  - `sftp_ordering_path` → ❌ 未 collect，且還沒被 production consume（VP-15460 stage 3b 未做）
  - `report_option` → ❌ 未 collect，但 DB default `CLASSIC`（不阻擋 live，可能給錯 report 格式）
- 結論：本 ticket approve/reject 只動 status，不該管 technical config；建議透過既有 `ConfigurationManagementService` (`PUT /:id/configuration`) 由 internal 在 approve 前補
- Doc § 9 列了 5 個 Open Questions 給 Leo + Kristine 討論

### [[VP-16629]] · _Lessons Learned_

### [2026-05-20]
1. **Ticket description 跟 PRD section 不一定一對一**：title + QA test ticket name + parent epic + reporter comment 都是 disambiguation 訊號。任一條不一致就 stop and clarify，不要硬解讀 description
2. **`.env DATABASE_URL` 可能指 prod 不是 dev**（lis-backend-emr-v2: `lisportalprod2.mysql.database.azure.com / lis_emr`）。Prisma migrate / db execute 前要：1) 確認 host 2) 驗證個別 schema element 存在 3) 看 `_prisma_migrations` table 是否存在
3. **Repo `/scripts/` 被 gitignored**：one-shot ts-node ops scripts 不入版控。Deploy-required 的 seed 邏輯該放 `prisma/seed.ts` 或 dump 成 SQL fixture 進 migration folder
4. **MySQL `utf8mb4_unicode_ci` collation 是 case-insensitive**：Prisma `where: { emrName: 'APRIMA' }` match 'Aprima'，不必 LOWER。但 underscore/format 差異（'ChARM_EHR' vs 'CHARMEHR'）要 multi-candidate
5. **server_folder 過濾 broad-then-narrow**：vendor SFTP path 命名混亂（`/Prod/Order/` 無 s、`/Order/` 無 leading、`/Orders/` 有 s 並存）。filter 用 `'order'` 不是 `'/orders'`
6. **Prisma migrate status「全部 unapplied」可能是假象**：若 `_prisma_migrations` table 不存在，status 把所有 migration 標未 applied 即使 schema 已 manual SQL apply。要 verify 個別 column/table 存在判斷實際狀態
7. **`ehr_integrations.legacy_emr_service` 為 result delivery 關鍵欄位**：result-generation fan-out 鍵之一是 `(legacy_emr_service, sftp_result_path) pair`。Fallback chain `ehr_vendor.code → legacy_emr_service → 'DEFAULT'`
8. **Cerbo (MDHQ) = practice-level integration model**：每 clinic 一 SFTP folder `/{clinicCode}/orders/` + `/{clinicCode}/results/`，folder 名由 PM 指定，approve 時 register 到 `sftp_folder_mapping`
9. **`sftp_folder_mapping.local_folder` 命名 convention**：`/{EmrName}/Prod/Order/` 或 `/Result/`（MDHQ → `/MDHQ/Prod/Order/`，ATHENA → `/ATHENA/Prod/Order/`）
10. **Approve 副作用 fire-and-forget**：approval = status transition 主動作；downstream config (sftp_folder_mapping upsert) 用 try/catch + log，避免半成品狀態
11. **Step 4 propose 三方案而非只 "pause + clarify"**：scope 看似不可能達成時，仍要 propose A/B/C。Leo 一句話可能釐清 scope，事實 ticket 可以 ship — 我若 pause 太久浪費 round-trip

---

## Git / branch / commit / push <a id='git-workflow'></a>

### [[INCIDENT-20260518]] · _Decisions Made_

### [2026-05-19] 直接 push staging branch
平常 Leo 規則禁止 push staging，但此 incident 緊急且 Leo 明確兩次授權。

### [[VP-15460]] · _User Feedback_

### [2026-04-28] Mid-execution corrections
- "你的 sftp_folder_mapping 改動還沒真的上傳到 database" — agent had only committed migration SQL; user wanted actual prod apply. Lesson: don't assume "release pipeline will handle it"; ask explicitly.
- "192.168.60.11:3306 也要 apply" — agent missed second DB; user reminded. Lesson: lis-emr-v2 schema lives in two MySQL instances (prod Azure + dev internal), both need migration apply.

### [[VP-15460]] · _Lessons Learned_

1. **`redlock@4` API + CommonJS interop pitfalls** → `patterns.md` (Node deps section)
2. **HL7 message type variant handling (OML_O21 ↔ ORM_O01)** → `emr-integration.md`
3. **`hl7_file_input` column width constraints** (emr_code_not_found 255, customer_not_found 45) → `emr-integration.md`
4. **lis-emr-v2 has two MySQL instances** (prod Azure + dev `192.168.60.11`) — migrations need applying to both → `patterns.md`
5. **Prisma migrations not baselined in prod** — `migrate deploy` returns P3005; use `prisma db execute --file` for raw SQL apply → `patterns.md`
6. **MyBatis hand-added statement pattern** (avoid generator regeneration loss) → `patterns.md`
7. **Bash tool cwd persists across calls** — explicit `cd` in cross-repo flows → `patterns.md`
8. **Validate dep instantiation, not just tsc** — `node -e "new Pkg(...)"` before deploy for new packages → `patterns.md`

### [[VP-16337]] · _Lessons Learned_

**`/scripts/` is gitignored** — new standalone test/verify scripts won't be tracked unless `git add -f`. Existing ~1396 tracked scripts predate the rule. Must decide per-ticket whether the script should ship with the change or stay local.

### [[VP-16361]] · _Lessons Learned_

### [2026-04-29]
- **ticket 已有 MERGED PR 不代表核心需求做完** — git log 看 commit 實際動的檔案，比 PR 標題或 ticket comment 可靠
- **Leo 自然語言指示要先列解讀分歧**（"participant 裡面有 patient" 可能是純結構檢查或含 caller 驗證）— 同時呈現兩種解讀並指出 AC 一致性，比假設後返工快
- **複雜 service method 的 auth path test** — spy method 內 downstream 呼叫 (e.g. `updateWholeEventRecord`) 短路後續流程，只測前段 auth 邏輯，避免 mock 整條 pipeline

### [[VP-16410]] · _Decisions Made_

### [2026-05-05 22:10] Leo 給出新方向（範圍擴展，非單純 rebuild reset service）
原 ticket 只說「rebuild Ziang's reset service + idempotent」，Leo 改成：
1. **強制 1:1**：v2_event.accession_ids 中每個 accession_id 只能綁一個 event（限 practice_id=150105）
2. **新表 (claim)**：建一張 table 記錄「已被 event 占用的 accession_id」
3. **Backfill**：把現有 v2_event (150105) 的 accession_id 全部寫入
4. **Hook into create flow**：createEvent / createEventByPatient (150105) 建 event 時同步寫入 claim
5. **Reset API**：新 endpoint 從 claim 表移除 accession_id（取代 Ziang 舊 service）
6. **Audit log table**：所有 accession_id 操作 history

### [[VP-16502]] · _Lessons Learned_

### 技術 (technical)
- **Cross-cutting helper 抽不乾淨時 in-place duplicate 比 over-DRY 好**：5 個 send method 每個 templateModel build 不同 fields（PRD 7 scenario × 2 recipient role 不互通），抽 helper 要 switch by `(notificationType, recipientType)` 變得醜；in-place 加 ~30-50 行 cross-recipient loop / method 讀起來更直白
- **Cross-recipient YAML mapping 模式**：每個 notificationType 下加 cross-recipient `recipientType` key，指向另一邊既有 Postmark id（不開新 template）— 用 in-file duplicate 比 YAML anchor 更易讀

---

## Other / uncategorized <a id='other'></a>

### [[INCIDENT-20260518]] · _User Feedback_

### [2026-05-19] Leo 指認 PDF 下載要 3 分鐘 timeout 不要 60 秒
→ c6555a7 拉到 180s × 3 attempt。

### [[VP-16337]] · _Lessons Learned_

### [2026-04-27 23:45]
**lis-backend-emr-v2 has TWO parallel proto trees** — always confirm which gRPC server hosts the RPC before editing:

### [[VP-16617]] · _User Feedback_

### [2026-05-14]
- "沒有提到就是 full integration" — don't override LTM default on integration_type based on vendor distribution patterns.
- "ticket 裡面寫了 ... 就不需要跟我確認" — values explicit in ticket text are final, skip re-confirmation.
- "ABC 分別是啥" — terse-mode user prefers short cross-references over reusing letter labels across questions.
- "要對齊 order_clients 和 java" — invariant rule for kit_delivery ↔ kits_options.
- "把 order_clients 重複 row 合併" — chose治本 over leave-alone for Q1.

### [[VP-16664]] · _Lessons Learned_

2. **Display-copy convention ≠ technical correctness.** A calendar date `"05/12/2026"` could mean different absolute days in different TZs, but display copy doesn't usually write "May 12, 2026 PDT". Only time-bearing strings (`"10:30 AM PDT"`, `"05/12/2026, 10:30 AM PDT"`) need TZ qualifier. Don't over-apply TZ embedding "for technical correctness" if the convention doesn't ask for it.

---

## Error handling / throw / log / silent <a id='error-style'></a>

### [[LBS-1487]] · _Lessons Learned_

1. **LBS- 是 Service Desk** — Zendesk 自動同步，reporter 是 app account。寫入 `ticket-routing.md`。
2. **Temp hotfix 偏好 hardcode**：當 user 明說「自己會改回來」或「臨時」，**不要**新增 env var / config 變數 / TODO comment — 最小變動 + Leo 手動 revert 即可。VP-future 若遇到類似 hotfix request，預設 hardcode 提案。
3. **env var fallback ≠ revert**：prod k8s configmap 已 hard-set env var 時，改 code 的 `||` fallback 預設值對 prod **無效**。要 revert prod 行為必須 (a) hardcode 完全忽略 env，或 (b) 改 k8s kustomization。LBS-1487 選 (a)。

### [[VP-15460]] · _User Feedback_

### [2026-04-27] Pre-execution decisions
- Clinic-level marker = `customer_id='-1'` (option A — match existing `result-generation` convention, no schema changes)
- NPI matching = direct `customer_npi` only (no `effective_npi` fallback — vendors only ever send individual NPI)
- Multi-pod count = 2 → redlock required
- Architecture = Hybrid (`@Cron`-as-trigger + BullMQ worker), not one-shot pipeline
- Cron schedule = keep 15-min parity with legacy
- `SaveToOldDB`/`emr_tracking_data` writes — not needed in v2 pipeline
- Shadow flag column = `sftp_folder_mapping.use_v2_pipeline` (folder-level, not customer-level — folder is the unit EMR-Backend processes)
- Cross-repo guard (EMR-Backend) — Leo asked agent to do it (B1)

### [[VP-16329]] · _Decisions Made_

**重要決策點:**
1. **8445 在 ticket provider 列表中且已存在 RESULT_ONLY**：要 UPDATE 升級為 FULL_INTEGRATION，不是 INSERT
2. **5 個全新 provider** (36816, 48203, 48201, 48199, 48202)：走 INSERT
3. **既有 8446, 8447 一併 align**（per Leo Step 4 確認）：
   - integration_type RESULT_ONLY → FULL_INTEGRATION
   - MSH06 8445 → 12212
   - archive_path 統一 `/sanctuary/results/archive/`
   - 補 sftp_ordering_path = `/sanctuary/orders/`
   - 補 ordering_enabled = 1
   - order_clients 補 emr_name=MDHQ, remote_folder_path=`/sanctuary/orders/`
4. **8445 archive_path 也要修**（從 `/MDHQ/Prod/sanctuary_input/` → `/sanctuary/results/archive/`）
5. **old_clinic_id**: same-practice 既有 = null → 新 record fallback null
6. sftp_folder_mapping: 全新建立 1 筆 `/sanctuary/orders/` (sftp_source_id=3)

### [[VP-16396]] · _Lessons Learned_

### [2026-04-30]
- **DB UPDATE transaction 加 pre-check sanity guard**：執行前 SELECT 當前狀態，與預期值比對，不符就 throw 阻擋。避免 STM/分析跟實際 DB 之間的時間差導致誤改。配合 prisma.$transaction rollback 可全套保護
- **MDHQ 升級 RESULT_ONLY → FULL_INTEGRATION 標準動作清單**：(1) integration_type, ordering_enabled (2) msh06 改 Practice ID (3) sftp_archive_path 改 `/{folder}/results/archive/` (4) sftp_ordering_path 補 `/{folder}/orders/` (5) requested_by 改 ticket_id, last_modified_by=Leo (6) order_clients.emr_name=MDHQ + remote_folder_path 補 (7) 檢查 sftp_folder_mapping 是否已存在

---

## Production safety / kafka / email / SFTP <a id='prod-safety'></a>

### [[INCIDENT-20260518]] · _User Feedback_

### Leo 明確否決方向（記得別再提）
- **不要再建議 emr-v2 切到 non-detailed batch** — Leo 強調 detailed 欄位（_l1~l6 abnormal level）對 HL7 有用，這條路否決了。

### [[VP-16396]] · _Decisions Made_

### [2026-04-30]
- 升級 RESULT_ONLY → FULL_INTEGRATION，single transaction
- Leo 要求執行前再 verify order_clients 與 sftp_folder_mapping 狀態 → 實作 pre-check sanity 阻擋（state 不符預期就拒絕執行）
- sftp_folder_mapping (id=165) 已存在不動

### [[VP-16664]] · _User Feedback_

### [2026-05-18]
- "不能改 yaml file 啊, email template端什麼都沒改, 重點是那些field要填入timezone" — **YAML schemas are templates' contract; don't add new fields when the spec is to enrich existing values.** I initially added `*_timezone` paired fields to YAML; Leo treated that as changing the email template surface. Correct interpretation: embed TZ in existing field VALUES.
- "time/timezone 不要混用造成時間錯誤" — Leo framed the correctness criterion as the durable invariant; both per-recipient and shared-TZ designs satisfy the math, but per-recipient is more robust because recipients don't have to consult the label and mentally convert. Confirmed pick = per-recipient.
- "consult_date 不用加時區，05/22/2026 PDT 是不需要的，只要時間或日期+時間有就可以" — date-only fields don't need TZ qualifier in display copy; only time-bearing strings (time, dateTime) carry the abbrev.

---

## Review flow / report format / approval <a id='review-flow'></a>

### [[VP-16165]] · _Lessons Learned_

### [2026-05-05 22:40] 流程
- **Step 2 Epic 調查必查 sibling**：JQL `parent = <epic>` 列出所有兄弟 ticket，看誰 own 哪個 phase / dependency 順序，避免錯認本 ticket 範圍。
- **Step 4 呈報方案時要主動 propose「最小可獨立交付片」**：不要只列「完整 vs 大合併」兩極，補一個「拿掉所有 dependencies 後的 thinnest slice」常常是 Leo 偏好。
- **Confluence PRD 過大時**用 `mcp__claude_ai_Atlassian__fetch` (markdown ARI form) 取代 `getConfluencePage`，後者 ADF JSON 易爆 token 限制。

### [[VP-16280]] · _User Feedback_

### [2026-04-23 18:05]
Leo review 指出兩個漏項（two missed follow-existing fields）:
1. `kit_delivery_option` 要 follow same-clinic 既有 — Leo 手動改好新 record = `BOTH_BLOOD_AND_NON_BLOOD`（同既有 2 筆）。script 的 Field Defaults 是 `NO_DELIVERY`，會漏這條。
2. `order_clients.old_clinic_id` 要 follow same-clinic 既有 — 查到既有 2 筆都是 `1002859`，已 UPDATE order_clients id=2280 old_clinic_id → 1002859。

---

## Testing / mock / verify <a id='test-style'></a>

### [[VP-16612]] · _Lessons Learned_

3. **Tests must be deterministic regardless of shell/`.env` state.** Leo runs jest under a shell that loads `.env`; CI/CD doesn't. `runReminders` test passed in VP-16391 review but failed in Leo's env. Always `delete process.env.<KEY>` in `beforeEach` for any env-dependent guard.

### [[VP-16617]] · _Decisions Made_

### [2026-05-14] Default to FULL_INTEGRATION + MSH=125536 per ticket text
- User direction: ticket text says "Practice ID 125536 ← MSH" — that's the answer, no need to re-confirm. Don't pause on values the ticket already specifies.
- User direction: "沒有提到就是 full integration" — LTM default applies, don't override based on vendor's RESULT_ONLY-heavy distribution (Elation has 42/43 LIVE rows as RESULT_ONLY but Leo treats per-ticket default authority).

---

## DB / SQL / FK vs derived column <a id='db-style'></a>

### [[VP-16474]] · _Lessons Learned_

### [2026-05-14]
- **Before designing a new column/field, check if an existing free-form field already carries the data shape**. `notes` here had no schema, FE already encoded other key/value pairs in it, and adding provider was a strict extension — zero BE cost.
- **The cheapest correct answer can be "do nothing in BE"**. Worth surfacing as an option in the Step 4 user-discussion phase, not just the implementation paths.
- Recorded the generalization in LTM `patterns.md` under "Before adding a new field, check if existing free-form field covers the use case".

---
