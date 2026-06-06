---
id: failures
type: ltm
category: technical
status: active
score: 0.0
base_weight: 0.9
urgency: 3
created: 2026-06-05
updated: 2026-06-05
links:
- INCIDENT-20260518
- INCIDENT-20260601-sftp-hang
- VP-15460
- VP-16337
- VP-16410
- VP-16520
- VP-16521
- INCIDENT-20260528
- LBS-1487
- LBS-1541
- VP-16165
- VP-16424
- VP-16474
- VP-16476
- VP-16766
- VP-16784-87
- INCIDENT-20260604-mdhq-stale-connections
- VP-16164
- VP-16251
- VP-16280
- VP-16289
- VP-16423
- VP-16463
- VP-16502
- VP-16713
- VP-16720
- VP-16193
- VP-16232
- VP-16329
- VP-16612
- VP-16664
- VP-16734
- INCIDENT-2604156666
- VP-16154
- VP-16617
tags:
- failures
- root-cause
- auto-generated
summary: Auto-aggregated failure index from 58 entries across STM
---

# Failure Index

> 自動生成自 `storage/short_term_memory/*.md` 的 `## Failures` 區段。
> 由 `scripts/extract-failures.py` 維護，手動編輯會被下次 run 覆蓋。
> Last updated: 2026-06-05 — total 58 entries

## Themes

- [Production side-effects (Kafka / email / SFTP)](#prod-side-effects) — 14 entries
- [DB / migration / backfill](#db-migration) — 11 entries
- [Other / uncategorized](#other) — 10 entries
- [Build / TypeScript / Tooling](#build-tooling) — 7 entries
- [Redis / cache / pending list](#redis-cache) — 3 entries
- [Deploy / commit / push coordination](#deploy-coordination) — 3 entries
- [Test / mock / spec](#test-mocking) — 3 entries
- [Auth / permission / role](#auth-permission) — 2 entries
- [Scope / requirement / PM communication](#scope-communication) — 2 entries
- [Tool / cwd / branch / repo confusion](#tool-usage) — 1 entries
- [Error handling / throw vs log](#error-handling) — 1 entries
- [gRPC / network / timeout](#grpc-network) — 1 entries

---

## Production side-effects (Kafka / email / SFTP) <a id='prod-side-effects'></a>

### **[[INCIDENT-20260528]]** — `2026-05-28` — Dead-host 假設錯誤、本地 TCP test 沒驗 actual port

我本機 `nc -z host 22` 測 PF + Breathermae 兩個 vendor 都 FAIL → 結論「dead host = hang 元凶」。實際 PF=2222、Breathermae=2222、MDHQ=2210。**用 port 22 測非標準 port 的 vendor 等於沒測**。VP-16180 STM 早就有「PF SFTP 45.24.217.150:2222」、我沒看。Leo 一句「我能連到」才回頭抓 `emr_sftp_source.port` 重測。

預防：任何 host reachability test 都先 `SELECT host, port FROM emr_sftp_source WHERE emrName=...` 取真實 port、別 hardcode 22。

### **[[INCIDENT-20260604-mdhq-stale-connections]]** — `2026-06-04 22:00` — First monitor.sh run mis-identified pod label

- Used `app=lis-emr-v2-deployment-prod` (deployment name) as label selector — actual label is `app=lis-emr-v2-prod` (`-deployment-` not in label).
- Tick 1 returned `FAIL pod_not_found`. Fixed by checking `--show-labels` and re-running.
- Lesson: always confirm label keys with `kubectl get pod ... --show-labels` before selecting; deployment-name ≠ pod-label.

### **[[VP-15460]]** — `2026-04-28` — redlock Lock API confusion (#90)

Picked `lock.release()` from redlock@5 docs while installing redlock@4. The two versions have different Lock prototypes (`unlock` vs `release`). Cosmetic in production (TTL covered the leak) but log noise + would have been a real bug if TTL was raised.

### **[[VP-16164]]** — `2026-05-27` — v1 schema 過度簡化（照 PRD 沒做完整盤點）

- v1 只給 practice 單一 sftp_path，漏掉 order/result pipeline 真正會用的十幾個欄位（傳輸方式/分開的 order/result path/enabled flags/legacy fields）。沒考慮 CharmEMR HTTP 模式。
- Root cause：照 PRD 的精簡 schema 直接做，沒先盤點「pipeline 實際讀 ehr_integrations 哪些欄位」。
- 修法：Leo 質疑後派 explore 做完整 pipeline 欄位盤點 + 真實資料 COUNT(DISTINCT) per-group 一致性分析，才知道哪些該 practice / 哪些 per-provider。
- **教訓**：要「取代既有表」的 schema，先盤點既有表在所有 pipeline 被讀的完整欄位清單，再設計。不要信 PRD 的精簡 schema。

### **[[VP-16164]]** — `2026-05-27` — COUNT(DISTINCT) 把 null 當一致的陷阱

一致性分析說 legacy_result_send_type「always consistent」，但 pipeline parity 抓到 1 個 group 有 [null, SFTP]。COUNT(DISTINCT) 忽略 null，所以判為一致。實際 backfill 把 null 正規化成 group 值。本案 pipeline 等價（null→SFTP）無害，但要記得 null 在一致性分析會被低估。

### **[[VP-16251]]** — `2026-04-21 21:50` — Script 產出的資料有 3 個問題需手動修正:

1. sftp_ordering_path = null（script 未設定）
2. sftp_archive_path 缺尾部 /
3. sftp_folder_mapping sftp_source_id = null（已修正）
4. 誤插 sftp_folder_mapping result mapping — sftp_folder_mapping 僅用於 ORDER（已刪除）

### **[[VP-16280]]** — `2026-04-23 18:05` — 兩個遺漏（both caught by Leo at review, not by agent）:

- 沒查 `kit_delivery_option` same-clinic 既有 → 預設 `NO_DELIVERY` 與 practice 實際 `BOTH_BLOOD_AND_NON_BLOOD` 不一致
- 沒查 `order_clients.old_clinic_id` → 新 record null，既有皆 1002859
Root cause: Step 5c 只查了 integration-level 欄位（report_option / integration_type / sftp paths），沒把 `kit_delivery_option` 和 order_clients 的 `old_clinic_id` 納入 same-practice-follow-existing 檢查清單。

### **[[VP-16289]]** — `2026-04-23` — - insert-ehr-integration.ts 第一次用錯參數格式 → 看 usage 後修正

- MDHQ 已知問題: sftp_archive_path 缺尾部 `/`、emr_name 小寫 → 手動 SQL 修正

### **[[VP-16423]]** — `2026-05-04` — kit_delivery_option 錯誤對齊 PENDING stub

- 錯誤決定：Phase 2 把 7 筆 ehr_integrations.kit_delivery_option 對齊 17412 PENDING stub 的 BOTH_BLOOD_AND_NON_BLOOD
- Root cause：誤把 PENDING stub（4/23 internal staff 預建、business 欄位全空）當「same-clinic 既有 LIVE」可 follow。實際 stub 的 kit_delivery_option 是 schema default（`@default(BOTH_BLOOD_AND_NON_BLOOD)`），不是真實設定
- prod 驗證：(kits_options=0, kit_delivery_option=NO_DELIVERY) 配對有 112 筆全部一致；其餘 (kits_options=0, BOTH) 579 筆是 schema default 沒明確覆蓋
- 正確規則：**kit_delivery_option 應對齊 order_clients.kits_options（runtime source of truth）**，0 → NO_DELIVERY
- 處理：`_apply-vp16423-kit-fix.ts` UPDATE 7 筆 → NO_DELIVERY（pre-check 通過）
- 預防：(a) PENDING / stub record 不算 same-clinic 既有可 follow；(b) 任何 ehr_integrations.kit_delivery_option 決策都先 check 對應 order_clients.kits_options 對齊

### **[[VP-16463]]** — `2026-05-13 15:46` — v2 NO_NPI parity break (RED FLAG, awaiting user decision)

Two post-expansion files stuck on v2 path with behavioral divergence from v1:

| file id | folder | received | customer_not_found | parse_finished | sample_id | retry_num | pod_name |
|---|---|---|---|---|---|---|---|
| 6053 | parsley-la | 2026-05-13 11:45 | NO_NPI | 0 | NULL | 5 | NULL |
| 6058 | ravelhealth | 2026-05-13 15:30 | NO_NPI | 0 | NULL | 5 | NULL |

**Past 7d MDHQ baseline** (31 success + 9 `no payment method` flags): ALL 40 v1-processed files have `last_update_pod_name='lis-emr-prod-*'` and `parse_finished=1` (even with non-success flags). NO files in entire 7d have `NO_NPI` flag — these 2 are unique.

**Three suspected v2 regressions**:
1. **NPI-check parity break**: v1 either skips NPI lookup or uses a different fallback. v2 explicitly rejects on missing NPI.
2. **Terminal-state retry bug**: v2 detected customer_not_found but didn't set parse_finished=1, so worker keeps retrying (5 attempts). v1 sets parse_finished=1 even with flag.
3. **Audit gap**: v2 worker not persisting `last_update_pod_name` on error path — cannot prove provenance.

**Cutover monitor cadence tightened to 30min** while red flag active.

**User decision options pending**:
- A: Rollback id=78/201 to use_v2_pipeline=0 (let v1 reprocess)
- B: Inspect HL7 file content for NPI presence (rule out data vs logic)
- C: Keep observing

DO NOT auto-rollback without explicit user approval.

### **[[VP-16502]]** — `2026-05-07` — AC4 過度字面化 PRD #3

- **錯誤推理**: PRD #3 寫 "Reminder 48h/24h/15m (To Provider)" 我直接讀為 "only Provider"，加 filter 後破壞 VP-16391 deployed 的「reminder 發所有 participant」設計
- **正確意思**: PRD 字面是「at minimum Provider」— Lab Team 也要收
- **Leo 糾正**: 「需要給 provider + clinician」
- **教訓**: PRD wording 沒 explicit "only X" 時不要加 filter，先確認語意；deployed prod 行為是 evidence，AC 跟既有 test 衝突優先 raise 再決定，不要「先加 filter 等 test 改」

### **[[VP-16713]]** — [2026-05-21 ~19:50] Calendar DB schema 混淆（critical insight）

- 我給的 audit query 在 Leo 的 client 跑出 0 列，因 client 連的是 `calendar_dev_new` schema（沒有這批 prod 資料）
- Wasted ~2 輪 query 嘗試，直到讓 Leo 跑 `current_schema()` 才確認
- Root cause: 我預設 Leo 連的就是 prod，沒先要求 enumerate schema
- 防範：calendar DB 操作**第一步**永遠先 `SELECT current_database(), current_schema()` 或 `SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'calendar%'`，這跟 repos.md 既有規則一致

### **[[VP-16713]]** — `2026-05-21 20:05` — 對 event 9509 的 query 邏輯誤判

- Leo 給 event 9509 raw data（明明有 clinicadmin participant 30789 Brooke）
- 我前面 query 用 `c.role IN ('provider','clinicadmin')` 邏輯**應該**返回 Brooke
- 我錯誤推測「event 沒有 clinician participant」，提議 creator-path fallback
- Root cause: 連 dev schema 而 prod schema 才有資料，是 schema 問題不是 query 邏輯問題
- Lesson: query 跑出空時，先驗證**連線 / schema / 資料存在性**，再懷疑 query 邏輯

### **[[VP-16720]]** — `2026-06-01` — order_clients 重複 INSERT（Anna 43262 ×4）

**症狀**：我 INSERT 24 order_clients（per pair），但 Anna 43262 跨 4 clinic 同 customer_id → 4 個重複 oc rows（ids 2303/2306/2309/2312）。

**Root cause**：[[VP-16766]] 是 single (cust, clinic) pair，沒呈現「跨 clinic 同 customer」場景，所以 STM 沒明確標 `order_clients` 是 **per-customer not per (cust, clinic) pair**。我直接按 pair × 1 INSERT 24 筆。

**Verify confirmed**：prod 「跨 2+ clinic 的 provider」全部都是 1 個 order_clients row（包含我 INSERT 前的 Anna 43262 應該也只有 1 row）—— 慣例明確。

**修法**：事後 deleteMany ids 2306/2309/2312，保留 2303。21 distinct customers / 21 oc rows ✓。

**Preventable**：是。pre-check 階段應該偵測 PAIRS 內重複 customer_id + 對 INSERT 邏輯 dedupe by customer。

---

## DB / migration / backfill <a id='db-migration'></a>

### **[[INCIDENT-20260604-mdhq-stale-connections]]** — `2026-06-04 22:00` — expect spawn syntax error with `{...}` jsonpath

- `kubectl get pods -o jsonpath='{.items[0].metadata.name}'` inside expect's `spawn` argument: expect interprets `{...}` as Tcl array.
- Fixed by switching to `--no-headers -o custom-columns=NAME:.metadata.name`.
- Lesson: avoid `jsonpath` with Tcl-significant chars in expect scripts; prefer custom-columns output for single-field extraction.

### **[[VP-16193]]** — `2026-04-17 18:30` — **insert-order-client.ts script bug: customer_id 設為 clinic_id 值**

- 問題: 執行 insert-order-client.ts 後，order_clients.customer_id = 6338（Practice ID）而非 5408（Provider ID）
- Root cause: script 內部將 customer_id 參數映射到 clinic_id 值，已知 bug
- 修正: 手動 SQL `UPDATE order_clients SET customer_id = 5408 WHERE id = 2278`
- 可預防: 是。未來執行 insert-order-client.ts 後必須驗證 customer_id 是否正確

### **[[VP-16232]]** — `2026-04-20 14:30` — **Failure 1: 用 crm.contacts 而非 gRPC**

- Error: 4,480 筆在 crm.contacts 找不到
- Assumption: crm.contacts 有所有 customer 資料
- Root cause: crm.contacts 只有部分 customer（可能只有 sales contacts），不是權威資料源
- Fix: 改用 gRPC GetCustomer

**Failure 2: 命名格式錯誤**
- Error: 把 patient calendar 改成 "{name}'s Provider Calendar"
- Assumption: 沒有確認現有命名慣例
- Root cause: 沒有先查看已存在的 patient calendar 命名格式（應為 "{NAME}'s Patient Calendar"）

**Failure 3: gRPC endpoint 錯誤**
- Error: CORE_SAMPLE_V2_RPC (10.224.0.53:8084) → ECONNREFUSED
- Assumption: .env 裡的值可以直接用
- Root cause: 沒有先讀 lis-code-agent/knowledge/emr-integration.md，那裡明確記載 gRPC endpoint 是 192.168.60.6:30276
- Fix: 用 knowledge 裡記載的 endpoint

**Failure 4: NestJS createApplicationContext + gRPC**
- Error: gRPC @Client decorator 在 CLI 模式不初始化，且 PublicBookingService.onModuleInit crash
- Assumption: 可以用 NestJS context 跑 gRPC migration
- Root cause: createApplicationContext 不啟動 microservice transport
- Fix: 改用 @grpc/grpc-js + proto-loader 直接建立 gRPC client

**Failure 5: 沒有使用 lis-code-agent knowledge**
- Error: 整個過程都沒有查 knowledge 目錄
- Assumption: 可以靠 .env 和 codebase 自己找到答案
- Root cause: 不知道/忽略了 lis-code-agent 的知識庫系統
- Fix: 任何 gRPC/migration 任務先讀 knowledge/

### **[[VP-16329]]** — `2026-04-27 23:00` — **Failure: 第二次重跑 36816 INSERT 觸發 duplicate constraint error。**

Root cause: 第一次跑時我用 `tail -50` 截取 output，後段顯示 record 資料但沒看到「✅ Successfully inserted」字樣（卡在 record dump），誤判沒成功就重跑。
影響: 無實質影響（script 在 unique check 時擋下，沒 partial insert）。
教訓: 確認 INSERT 成敗應 grep `Successfully|Error|❌` 而非看 record dump。後續 4 個 INSERT 都用 grep 過濾，順利完成。

### **[[VP-16410]]** — `2026-05-06 02:50` — 誤解 Leo「過去的 event 無需更動」為「rollback backfill」

- **錯誤推理**：Leo 說「過去 event 無需更動」我誤解為「backfill 不應該存在」，提議 DELETE 2350 claim + 2670 audit
- **正確意思**：「不要 update / delete 既有 v2_event row」— backfill 進 claim 表的 row 是新表新資料、不是 update 既有 event
- **Leo 糾正**：「未來如果有 accession_id 已經在 claim table 的還要創建 event 需要擋下來」— 暗示 claim table 的歷史資料是必要的（沒 backfill 就沒資料可擋）
- **教訓**：「過去的 event 無需更動」= 不動 v2_event 表本身，**跟 claim table 是否要 backfill 無關**。下次遇到否定句指令要拆「動什麼 / 不動什麼」維度，不要把 scope 自動擴到無關的 table

### **[[VP-16423]]** — `2026-05-04` — insert-ehr-integration.ts 對 25467 的 transaction 全 rollback

- 錯誤：`Duplicate order_client exists for NPI '1356634760' + clinic_id '19583'`
- 當時假設：以為 ehr_integrations INSERT 跟 order_clients INSERT 是分開 step，order_clients fail 不會影響 ehr_integrations。實際 script 用 `prisma.$transaction` 包成一包，order_clients duplicate check 拋 → ehr_integrations 也被 rollback。
- Root cause：script duplicate 檢查依「customer_provider_NPI + clinic_id」（不是 customer_id + clinic_id + ehr_vendor_id），對「同人多 customer_id」case 不友善
- 處理：Phase 2 raw SQL 繞過 check，ehr_integrations 用 cuid library 自生 ID，order_clients 直接 INSERT。
- 預防：未來 ticket 若 provider list 有 same-NPI 重複，先警告 script 對 25467 case 的 order_clients 必失敗，預備 raw SQL fallback

### **[[VP-16502]]** — `2026-05-07` — 抽 helper 沒做（合理 trade-off）

- 5 個 send method cross-recipient loop 結構幾乎一樣（差 templateModel build），原本想抽 helper 集中
- 但每個 method 的 templateModel fields 不同（PRD 7 種 scenario × 2 個 recipient role 的 fields 不互通），抽 helper 要 switch by `(notificationType, recipientType)` 變得 ugly
- 採 in-place duplicate（5 個 method 各加 ~30-50 行）— 雖然 DRY 不滿足但 readability 更高
- 沒算失敗，但記下「複雜 templateModel build 的 cross-cutting helper 抽得不乾淨時，in-place 直白比 helper 好」

### **[[VP-16612]]** — `2026-05-18` — Initial proposed spec was wider than necessary

At Step 4 I proposed `role === 'provider'` (strict). Leo refined to "exclude (clinic_id=150105 AND clinicadmin)". My version would have silently changed patient-role behavior; Leo's preserves it. Lesson: when translating PM natural language ("only X, not Y") into code, prefer narrow exclusion of Y over broad inclusion of X — the former preserves the unconstrained set.

### **[[VP-16664]]** — `2026-05-18` — First-pass YAML schema change

I added `*_timezone` paired fields to both YAML files at Step 5 start, planning to use them in templateModel. Leo immediately reverted with "不能改 yaml file 啊". Root cause: I conflated "BE config describing template variables" with "Postmark template body in Postmark cloud" — Leo treats the YAML AS the template-end contract; adding fields there is an API change even if Postmark template body doesn't reference them. Lesson: when spec says "embed timezone", default to enriching existing values, NOT adding paired fields.

### **[[VP-16720]]** — `2026-06-01` — INSERT 新 row 漏借 same-customer NPI

**症狀**：3 個新建 Anna pair (2930/8003/36290) customer_npi 寫 null（理由：ticket 表沒列 NPI 欄）。Leo 指出 144510 既有 Anna row 的 customer_npi=1073000691 — 同 customer 跨 clinic NPI 應一致，3 個新 row 該借這個值。

**Root cause**：我的 sibling-borrow 邏輯只從 **same-clinic sibling** 取（borrow clinic_name / address / contact 等 clinic-level 欄位），沒考慮 **same-customer sibling**（不同 clinic 但同 customer_id）—— 那裡有 customer-level 欄位（customer_npi）。

**修法**：事後 `UPDATE customer_npi + effective_npi WHERE customer_id='43262' AND clinic_id IN (2930,8003,36290)`。3 row 補上。

**Preventable**：是。INSERT new pair 前應該分兩個 sibling lookup：
- same-clinic（任一）→ borrow clinic_name, address, contact_*
- same-customer 任一 LIVE row → borrow customer_npi, clinic_npi, effective_npi（如果有）

### **[[VP-16734]]**

（無實作層失敗）

**Minor procedural slip**:
- Probe script `_vp16734-check.ts` 初版查 `ehr_integration_status_history` 用 column `ehr_integration_id`（推測），實際是 `integration_id` — 一次 retry 後補上 information_schema 查欄位名再改。教訓：跨表的 FK column 命名不要憑猜，先 `SHOW COLUMNS` / information_schema 看 schema

---

## Other / uncategorized <a id='other'></a>

### **[[INCIDENT-20260528]]** — `2026-05-28` — 把 hang pod log 燒掉了

Leo 授權「(1) restart + (2) code fix」、我直接 `kubectl rollout restart`、**舊 pod (`6cc4674b87-ccgbf`) 的 log 隨 pod GC 永久消失**。/var/log/pods 對應目錄 mtime 還在但 log file 已清。所以「哪個 folder 是 5/27 真正 hang 元凶」**現場證據燒掉了**。後來 21:45 tick log 出來的 id=260 反而是 transient = 不是同一個 hang。

預防：destructive ops (rollout restart / pod delete) 前必須 `kubectl logs <pod> > /tmp/preserve.log` + `kubectl describe pod <pod> > /tmp/preserve_describe.txt`。已寫進 user memory feedback。

### **[[LBS-1487]]**

無。

### **[[LBS-1541]]**

(none yet)

### **[[VP-16165]]**

_(尚未 execute)_

---

### **[[VP-16424]]**

（無實作層失敗）

**記憶層 failure**：Step 4 呈報時引 VP-16423 STM line 173「kit_delivery_option=BOTH_BLOOD_AND_NON_BLOOD（follow 17412 既有值）」當作 same-practice follow 範例 — 但實際 DB query 17412 與其他 6 provider 全部都是 NO_DELIVERY。Root cause：VP-16423 STM Decisions 區段是早期決策草稿，最終 Leo 在 Step 6 review 時把全部 7 筆改 NO_DELIVERY 但 STM Decisions 沒同步 update（LTM `emr-integration.md` line 436 反而有寫對）。教訓：**引 STM 的決策內容前先用 DB 實際值 cross-check**，特別是時間久的 STM。

### **[[VP-16474]]**

_None._

### **[[VP-16476]]**

_(無 execution failure。Mistakes 在 Retrospective)_

---

### **[[VP-16521]]** — `2026-05-28 17:52` — git stash push 把 MERGE_HEAD 弄丟

- **症狀**：merge in-progress 時 `git stash push` → MERGE_HEAD 消失，stash pop 報 `event.service.ts: needs merge`
- **修法**：`git merge origin/stage_test --no-commit --no-ff` 重觸發 merge state，再 `git checkout stash@{0} -- src/calendar/models/event/event.service.ts` 把 stash 內的 resolved 版本拉回，最後 `git stash drop`
- **教訓**：merge in-progress 時禁用 `git stash`；要保存 in-flight diff 改用 `git diff > /tmp/wip.patch` + 該 file 個別 checkout
- **更好做法**：根本不該為了 "比較 pre-merge lint baseline" 中斷 merge state — 直接看 origin/feature 上的 ESLint baseline 即可，或先 commit 中間態再分析

### **[[VP-16766]]** — `2026-05-27` — **Minor TS slip**：`_apply` 腳本初版用 `${ehr.created_at = now}`（賦值表達式）想偷塞欄位，TS2339 編譯失敗。改成直接 `${now}`。教訓：raw SQL 的 template binding 不要塞賦值/副作用，值先算好再代入。



### **[[VP-16784-87]]**

（無 — verification-only session）

---

## Build / TypeScript / Tooling <a id='build-tooling'></a>

### **[[INCIDENT-20260518]]** — [2026-05-18 後續] 看到 c0852d0 部署後 Leo 仍見舊行為，沒立刻意識到 image age

**錯誤**：看到 prod log 還有 `Using fallback data` 就以為 fix 沒效。
**實際**：prod pod 還沒 rollout，跑的是舊 image。Image build + push + pod restart 大約 15-20 分鐘。
**Preventable**：是。下次 deploy 後先 `kubectl exec ... grep -c <新 marker> /app/dist/...js` 驗證 dist 真的有新 code。

### **[[VP-15460]]** — `2026-04-27` — Wrong proto file edited initially

Edited `src/proto/customer.proto` (`package lis`, legacy LIS host) before realizing v2 RPC lives in `src/proto-v2/customer.proto` (`package coresamples_service`, coreSamples host). Reverted both `proto/` + `dist/proto/` and applied to `proto-v2/`. Detection trigger: reading `src/config/grpc.config.ts`. Lesson already in `long-term-memory/patterns.md` (under "lis-backend-emr-v2 雙 proto 樹").

### **[[VP-15460]]** — `2026-04-28` — redlock CommonJS interop (#88)

Production NestFactory crash at startup: `TypeError: redlock_1.default is not a constructor`. Root cause: `redlock@4` is plain CommonJS (`module.exports = Redlock`, no `.default`); this repo's `tsconfig.json` only sets `allowSyntheticDefaultImports`, not `esModuleInterop`, so `import Redlock from 'redlock'` compiled to `redlock_1.default` (undefined). Should have caught this at code review by recognizing redlock's package age + checking `tsconfig`.

### **[[VP-16337]]** — `2026-04-27 23:38` — **Mistake:** Initially added the new RPC + messages to `src/proto/customer.proto` and `dist/proto/customer.proto`.

**Root cause:** Two parallel proto trees exist in this repo:
- `src/proto/customer.proto` — `package lis;`, used by v1 client connecting to legacy LIS gRPC `192.168.60.6:30276` (`grpcConfig.customer`)
- `src/proto-v2/customer.proto` — `package coresamples_service;`, used by v2 client connecting to coreSamples `10.224.0.199:32100` (`grpcConfigV2.customer`)

`GetClinicIDsByNPINumber` lives only in coreSamples — must go into proto-v2.

**Recovery:** Reverted both `src/proto/` and `dist/proto/` edits, then applied the changes to `src/proto-v2/customer.proto` only (no `dist/proto-v2/` exists, so single file).

**Detection trigger:** Reading `src/config/grpc.config.ts` for endpoint info — saw `getProtoV2Path` and `package: 'coresamples_service'` for the v2 customer client.

### **[[VP-16410]]** — `2026-05-06 11:00` — 在 repo root scripts/ 放 .ts 檔，破壞 nest build dist 結構

- **症狀**：Leo 跑 `npm run start:dev` 報 `Cannot find module '../../prisma2/generated/client2'`
- **誤判**：第一波分析以為是 prisma2 client + postbuild 沒 copy prisma2/ 的 repo 既有 bug，提了 quick fix `cp -r prisma2 dist/`
- **真正根因**：我寫的 `scripts/vp-16410-integration-test.ts` 是放在 repo root `scripts/` 下的 TypeScript file，tsc 預設沒 exclude 這目錄 → 把 `scripts/*.ts` 跟 `src/*.ts` 都 include → 為避免 output 衝突，dist 結構從**扁平**的 `dist/main.js + dist/trans/...` 變成**嵌套**的 `dist/src/main.js + dist/src/trans/... + dist/scripts/...`。`prisma2.service.ts` 用相對路徑 `'../../prisma2/generated/client2'` import，從 `dist/src/trans/` 出發解析 → `dist/prisma2/generated/client2`（不存在）。原本扁平結構從 `dist/trans/` 出發解析 → `LIS-transformer-v2/prisma2/generated/client2`（git tracked，存在）
- **修法**：把 `.ts` script 移到 `~/vp-16410-integration-test.ts.local-backup`，重 build dist 結構就恢復扁平
- **教訓**：
  1. 在 repo root scripts/ 寫 utility 一律用 `.js`（call PrismaClient JS API 即可，不用 ts-node 也能跑）；要寫 TypeScript 就放 `src/` 之外、且加進 `tsconfig.build.json` 的 exclude
  2. 跟 tsc/nest build 路徑解析有關的 bug：先看 `dist/` **頂層結構**（有沒有多/少一層），比 grep import path 更快
  3. user 強調「之前能跑」+ `git diff` 空時，要把搜尋範圍擴到 **untracked .ts 檔可能改變 tsc include scope** 這條軸

### **[[VP-16520]]** — `2026-05-28` — 把自己造成的 prisma client drift 誤判為「stale 假象」

- 現象:LIS-transformer-v2 我的 branch 上 `npm run build` 跑出 18 個 `specialties` 型別錯誤(node_modules/.prisma/client v2_calendar.specialties)。schema.prisma 沒 specialties、Calendar GraphQL model 沒、我 diff 也沒。
- 我下了「stale generated client 假象,build prebuild `prisma generate` 後就 0」的結論。
- Leo 糾正:「不可能,npm run start:dev 100% 要過,鐵律」「以前也有過以為是別人的問題,後來是自己創的」「找,找到為止」。
- 真因:之前在 `feature/leo/VP-16499` branch 工作時(那邊 schema 有 specialties)跑過 `prisma generate` → client 寫進 node_modules → 切到 VP-16521 branch(schema 沒 specialties)後 **client 沒重生成** → drift。**本 repo `npm run build` 的 prebuild 只是 `rimraf dist`,根本不會跑 prisma generate**(我先前以為會,完全錯)。
- 修法:`npx prisma generate` + `npx prisma generate --schema=prisma2/schema2.prisma`(雙 client)→ build 0 → start:dev 啟動成功。
- 教訓:已寫進 user memory `feedback_start_dev_iron_rule.md` + LTM repos.md。**「壞掉 = 自己造成的」要當預設假設**;切 branch 後不同 schema 必跑 generate 對齊雙 client。

### **[[VP-16521]]** — `2026-05-28 17:50` — 分析 start:dev 走錯一輪 quick-fix（VP-16410 lesson 沒第一時間 retrieve）

- **症狀**：merge 完跑 `npm run start:dev` 報 `Cannot find module '../../prisma2/generated/client2'`
- **誤判**：第一波先做 dist 結構分析 → 提出 nest-cli assets / path-alias 等 4 個 option 問 Leo
- **真正根因**：scripts/_send-reschedule-preview-emails.ts（VP-16521 上一輪留下的 untracked .ts）讓 tsc include 抓到 scripts/，dist 變 `dist/src/...` 嵌套（**完全跟 VP-16410 incident 同一個雷**）
- **可預防**：Step 1 Retrieve 時 grep `failures.md` for `start:dev|MODULE_NOT_FOUND|prisma2.*client2` 應該秒中
- **教訓**：start:dev 失敗時，**第一動作是 `ls dist/` 看頂層結構**（有沒有多/少一層 `src/`），不是 grep import path 或 prisma generate

---

## Redis / cache / pending list <a id='redis-cache'></a>

### **[[INCIDENT-20260518]]** — `2026-05-18 14:00` — 第一輪 root cause 推錯：Redis emptyDir wipe

**錯誤假設**：Redis sidecar `emptyDir` → pod restart 丟 queue → DB record 變孤兒。
**實際**：Redis 沒被 wipe，job 還在 Redis、worker 沒消費。
**Root cause**：沒先看 BullMQ queue stats (`LLEN waiting`, `LLEN active`, `processedOn`)，直接從 architecture review 推測。
**Preventable**：是。下次先 `redis-cli` 查 queue 實況再下結論。

### **[[INCIDENT-20260518]]** — `2026-05-19` — 建議 `kubectl delete pod` 沒事先警告新 pod 一樣會踩同樣 Redis 坑

雖然新 pod jjk9d 確實踩同樣 Redis NXDOMAIN handler hang，但 Leo 是基於我的建議做的、沒得到預期收益。
**Preventable**：是。對 stateful upstream dependency 的 pod restart 應該預警「新 pod 跟舊 pod 跑同 image 同 ConfigMap，如果問題在 ConfigMap / 環境，restart 沒用」。

---

### **[[INCIDENT-20260601-sftp-hang]]**

- 5/30 INCIDENT-20260528: identified same symptom but only documented "Required pod rollout restart". Root cause was not traced into the singleton/await chain. Recurrence on 6/1 demanded deeper investigation.

---

---

## Deploy / commit / push coordination <a id='deploy-coordination'></a>

### **[[INCIDENT-20260518]]** — `2026-05-19` — 寫 logging 跟 timeout 但沒先說「現在不用 build」

Leo 急著補發、不想 build。我多次 commit + push 沒先問是否需要 deploy。後來 Leo 主動講「現在不用 build」才停下。
**Preventable**：是。緊急 incident 過程中 commit ↔ deploy 是兩個分離決策，要先確認再做。

### **[[INCIDENT-20260528]]** — `2026-05-28` — Migration apply 漏 staging DB

VP-16760 創 `ehr_vendor_inquiry_status_history` table、migration SQL commit 進 repo、但只 apply 到 prod DB (`lisportalprod2`)、漏 apply staging DB (`192.168.60.11`)。今天 staging 部署後 FE call reject endpoint 才爆 P2021 500。

LTM patterns.md 304-308 行早就有「兩 DB 都要 apply」、但實際上線時還是踩了 — 因為**沒有自動化驗證機制**、純靠人記得。已建議寫進 Jenkinsfile pre-deploy。

### **[[VP-15460]]** — `2026-04-28` — Migration not applied automatically

Agent committed migration SQL to repo and assumed release pipeline would `prisma migrate deploy` it. Leo had to remind: "你 sftp_folder_mapping 的改動還沒真的上傳到 database". Then `prisma migrate deploy` failed with P3005 (DB never baselined for prisma migrations) → fell back to `prisma db execute --file <sql>` (raw SQL apply). Then "192.168.60.11:3306 也要 apply" — second DB. Lesson: this repo has two MySQL instances + Prisma is not the migration source-of-truth in prod.

---

## Test / mock / spec <a id='test-mocking'></a>

### **[[INCIDENT-2604156666]]** — `2026-05-21` — spec 在 HEAD 已壞（pre-existing，Leo 要求併本 hotfix 修）

- `sample-test-result.service.spec.ts` HEAD 是 6/6 fail，多層 stale：
  1. **DI 缺 provider**：service constructor 注入 AbnormalFlagCalculatorService + ResultStatusMapperService，spec 從來沒提供 mock → `Nest can't resolve dependencies` → 全部 test setup 階段 fail
  2. **4b10e1a 後 Step 5 primary 變 cloud**：spec 只 mock 了 `getTestResultsDetailedData`（on-prem fallback），`getTestResultsDetailedDataCloud` 沒 mock → 4 個跑 full flow 的 test 在 Step 5 拿到 undefined
  3. **referenceRange mock shape 過期**：service buildTestResults 讀 `result.normalRange.referenceRange`，spec 寫的是舊 `result.allList[i].referenceRange`
  4. **`getPatientReferenceRange` 真實 payload 是 snake_case + 帶 `result_value`**，spec 期望 camelCase 不帶 result_value
  5. **「無 reference range」`abnormalFlag` 預期錯**：Service 對齊 Java `getMasterListInfo()==null` 返回 `''`，但 spec 期望 `'N'`
- 全部本 commit 一次修齊，6/6 pass

### **[[VP-16154]]** — `2026-05-11 19:00` — - `event.service.spec.ts` 跟 `meeting-request.service.spec.ts` 用 `new ServiceClass(...)` 直接 instantiate（不走 DI），baseline 上已經缺一個 arg（pre-existing），加 settingTool inject 後 spec compile error 浮現。修法：spec 補 mock arg。



### **[[VP-16612]]** — `2026-05-18` — Pre-existing test broken by env state

`runReminders` test broke during local jest run because Leo's shell `.env` has `platform_type=local`, triggering early-return in `runReminders()`. This wasn't related to my changes but the existing test was env-dependent. Fixed with 1-line `delete process.env.platform_type` in `beforeEach`.

Root cause: VP-16391's test was written assuming `process.env.platform_type` undefined in jest. Works in clean CI/CD, breaks under `.env`-aware shell.

---

## Auth / permission / role <a id='auth-permission'></a>

### **[[INCIDENT-2604156666]]** — Lessons for testing

- `.spec.ts` 文件不能信賴 — 跟 service code 不同步演進（4b10e1a + 多次 service refactor 都沒同步 spec），可能長期沒人跑
- 應該每個 PR 跑該 service spec；或者 CI gate 上有 spec 必過要求

### **[[VP-16617]]** — `2026-05-14` — kit_delivery_option mis-set on first finalize

Set `kit_delivery_option=NO_DELIVERY` + `kits_options=0` following LTM line 454 and `_apply-vp16424-finalize.ts` template. Both sources were wrong (LTM bug + VP-16424 template propagated the same bug). Caught only after live-applied via cross-check with ParseHL7.java source.

Root cause: LTM had two conflicting statements (mapping table at line 173-176 correct, stub finalize default at line 454 wrong). I followed line 454 without spotting the conflict. Lesson: when LTM has two statements that should agree, verify against authoritative source (Java code here).

---

## Scope / requirement / PM communication <a id='scope-communication'></a>

### **[[VP-16617]]** — `2026-05-14` — First categorization of 87 dup combos used wrong pattern detection

SQL `COUNT(DISTINCT emr_name)` ignores NULL, so combos with `[NULL, 'PF']` looked like "same emr_name" in audit. Re-wrote categorization with JS `new Set` (treats null as distinct) → revealed 84 combos in "diff emr (one NULL)" pattern previously misclassified as "diff kits".

### **[[VP-16664]]** — `2026-05-18` — Initial date-also-with-TZ assumption

At Step 6 review I included `consult_date: "05/12/2026 PDT"`. Leo corrected to "date does not need TZ; only time-bearing strings do". My reasoning was "dates cross midnight differently in different TZs so date should carry TZ" — technically true but display-copy convention does not write dates with TZ. Lesson: distinguish display-copy convention from technical correctness; the latter does not always require the former.

---

## Tool / cwd / branch / repo confusion <a id='tool-usage'></a>

### **[[VP-15460]]** — [2026-04-27 → 28] Cwd persistence in Bash tool calls

After `cd /Users/hung.l/src/EMR-Backend && gh pr view 156`, subsequent Bash calls without explicit `cd` defaulted to EMR-Backend. Created `bugfix/leo/VP-15460-redlock-import` in the wrong repo, had to clean up. Lesson: always explicit `cd` in cross-repo flows.

---

## Error handling / throw vs log <a id='error-handling'></a>

### **[[VP-16154]]** — `2026-05-11 19:15` — - 第一次 helper 用 `throw new Error('...')` 對 missing header — Leo 要求「沒新 data 不報錯」後改成 try/catch + log.warn + return undefined。



---

## gRPC / network / timeout <a id='grpc-network'></a>

### **[[VP-16521]]** — `2026-05-28 17:53` — IDE diagnostics 不穩（mcp__ide__getDiagnostics 連續 timeout）

- 試 2 次都 timeout，改跑 `npx eslint <file>` CLI 直接拿同樣結果
- 教訓：WebStorm 抓 lint 等於 eslint + prettier；agent 端不要等 IDE diagnostics，CLI 更快更穩

---
