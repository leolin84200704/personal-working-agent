---
id: failures
type: ltm
category: technical
status: active
score: 1.2597
base_weight: 0.9
urgency: 3
created: 2026-08-16
updated: 2026-08-20
links:
- INCIDENT-20260518
- INCIDENT-20260528
- INCIDENT-20260601-sftp-hang
- INCIDENT-20260604
- INCIDENT-20260604-mdhq-stale-connections
- INCIDENT-20260817-onprem-deploy-freeze
- INCIDENT-2604156666
- LBS-1541
- LIS-7690
- PO-222
- PO-256
- QH-1104
- QH-1130
- QH-1159
- QH-1591
- QH-1775
- QH-211
- QH-2259
- QH-2648
- QH-680
- QH-862
- QH-918
- QH-919
- VP-15460
- VP-16164
- VP-16168
- VP-16169
- VP-16172
- VP-16193
- VP-16232
- VP-16251
- VP-16280
- VP-16329
- VP-16337
- VP-16391
- VP-16499
- VP-16513
- VP-16514
- VP-16516
- VP-16520
- VP-16521
- VP-16629
- VP-16689
- VP-16720
- VP-16734
- VP-16759
- VP-16760
- VP-16766
- VP-16784
- VP-16785
- VP-16786
- VP-16787
- VP-16859
- VP-16921
- VP-16934
- VP-16945
- VP-16968
- VP-16980
- VP-16987
- VP-17065
- VP-17076
- VP-17120
- VP-17217
- VP-17222
- VP-17283
- VP-17312
- VP-17412
- VP-17421
- VP-17422
- VP-17497
- VP-17524
- VP-17532
- VP-17544
- VP-17559
- VP-17561
- VP-17577
- VP-17591
- VP-17685
- VP-17714
- VP-17715
- VP-17748
- VP-17765
- VP-17812
- VP-17825
- VP-9299
- business-model
- business-model-deep
- feedback_batch_db_verify
- feedback_defect_found_must_be_ticketed
- feedback_join_scope_reverse_audit
- feedback_never_conclude_breakage_from_a_quiet_window
- feedback_start_dev_iron_rule
- repo-catalog
- repos
tags:
- failures
- root-cause
- auto-generated
summary: Auto-aggregated failure index from 77 entries across STM
---

# Failure Index

> 自動生成自 `storage/short_term_memory/*.md` 的 `## Failures` 區段。
> 由 `scripts/extract-failures.py` 維護，手動編輯會被下次 run 覆蓋。
> Last updated: 2026-08-20 — total 77 entries

## Themes

- [Production side-effects (Kafka / email / SFTP)](#prod-side-effects) — 22 entries
- [Other / uncategorized](#other) — 12 entries
- [Build / TypeScript / Tooling](#build-tooling) — 10 entries
- [DB / migration / backfill](#db-migration) — 8 entries
- [Deploy / commit / push coordination](#deploy-coordination) — 6 entries
- [Redis / cache / pending list](#redis-cache) — 4 entries
- [Scope / requirement / PM communication](#scope-communication) — 4 entries
- [Error handling / throw vs log](#error-handling) — 3 entries
- [Test / mock / spec](#test-mocking) — 2 entries
- [Auth / permission / role](#auth-permission) — 2 entries
- [gRPC / network / timeout](#grpc-network) — 2 entries
- [Tool / cwd / branch / repo confusion](#tool-usage) — 1 entries
- [GraphQL / API design](#graphql-api) — 1 entries

---

## Production side-effects (Kafka / email / SFTP) <a id='prod-side-effects'></a>

### **[[INCIDENT-20260528]]** — `2026-05-28` — Dead-host 假設錯誤、本地 TCP test 沒驗 actual port

我本機 `nc -z host 22` 測 PF + Breathermae 兩個 vendor 都 FAIL → 結論「dead host = hang 元凶」。實際 PF=2222、Breathermae=2222、MDHQ=2210。**用 port 22 測非標準 port 的 vendor 等於沒測**。VP-16180 STM 早就有「PF SFTP 45.24.217.150:2222」、我沒看。Leo 一句「我能連到」才回頭抓 `emr_sftp_source.port` 重測。

預防：任何 host reachability test 都先 `SELECT host, port FROM emr_sftp_source WHERE emrName=...` 取真實 port、別 hardcode 22。

### **[[INCIDENT-20260604-mdhq-stale-connections]]** — `2026-06-04 22:00` — First monitor.sh run mis-identified pod label

- Used `app=lis-emr-v2-deployment-prod` (deployment name) as label selector — actual label is `app=lis-emr-v2-prod` (`-deployment-` not in label).
- Tick 1 returned `FAIL pod_not_found`. Fixed by checking `--show-labels` and re-running.
- Lesson: always confirm label keys with `kubectl get pod ... --show-labels` before selecting; deployment-name ≠ pod-label.

### **[[LIS-7690]]** — `2026-08-18 18:20` — on-prem configmaps hold plaintext secrets — grep them narrowly

`kubectl get cm -A -o yaml | grep -i lis-emr-v2` dumps `lis-emr-v2-config{,-prod}` in full, and
their `data` carries prod DB URLs with passwords, `JWT_SECRET`, Kafka SAS connection strings,
Adobe/OAuth client secrets and long-lived `VIBRANT_API_TOKEN` bearers in cleartext. Nothing was
persisted from that output. Next time select fields (`-o jsonpath` on the specific keys) instead
of grepping whole configmaps.

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

### **[[VP-16921]]**

- F1: Concluded "not a bug, customer misremembered" from a clean prod DB — WRONG. The bug (cancel cascade + a second producer) had erased/never-wrote the prod evidence. Corrected only after reading the customer's actual reminder screenshot (Leo supplied).
- F2: Theorized "zombie from 5/22 cancel-and-rebook left is_canceled=false" — WRONG (git showed rescheduleClinicalConsult sets is_canceled=true, and it was deployed 6/2 anyway). The real producer was a different env entirely.
- F3: Assumed the local `.env` calendar_prod = the only/authoritative prod DB and that all senders write there. Missed that a separate cluster could send to the same prod email topic without touching prod's DB.

### **[[VP-16934]]** — `2026-06-10` — VP-16940 result PULL 實作完成（read-only FHIR DiagnosticReport）

- `GET /api/v1/fhir/DiagnosticReport?sampleId=N` → 解析 `result_transmission_records.generated_hl7_content`(HL7 ORU) 轉 FHIR R4 DiagnosticReport（read-only，不刷卡/寫/送）。
- 新 module `src/modules/fhir-result/`：`Hl7ToFhirMapperService`（ORU→DiagnosticReport + contained Patient/Specimen/Observation(per OBX)/Practitioner/Organization；**PDF→presentedForm url 參照、不夾 base64**）、service（讀 record + per-client scoping）、controller（JwtAuthGuard + `FHIR_RESULT_MODE` flag 預設 disabled→403）。`FhirResultModule` **import AuthModule**（記取 CrashLoop 教訓）；註冊進 app.module。
- **關鍵發現**：實際 `raw_result_data` 只是輕量稽核 blob（無 patient/test 細節）→ 完整資料在 `generated_hl7_content`，所以 mapper 直接解析 HL7。
- **completeness（要求「除 PDF 外所有 HL7 都在 FHIR」）**：對 **8 筆真實 prod record** 逐 token 驗證 → **全 0 not-found**（含 929-obs 大報告）。補了 provider 姓名(ORC-12/OBR-16/PV1-7)、ORC-17 entering org、OBX-15 producer、MSH-10 control id。CI guard: `hl7-to-fhir.mapper.service.spec`。
- **本地 npm run start:dev e2e**（POD_ROLE=pusher 安全關掉 intake cron/kafka；FHIR_RESULT_MODE=enabled；連 prod 唯讀）：401/400/**200**（DiagnosticReport, 159 obs, PDF url 無 base64, contained 齊全）。
- 8 unit tests + build + DI boot check + 全套無新增失敗。config 兩份加 `FHIR_RESULT_MODE: disabled`（gitignored）。
- **PR #159**(base staging) + Story **VP-16952**(掛 Epic VP-16934)。未 merge。PUSH 留後續。

### **[[VP-16968]]** — `2026-06-11` — backfill type 設錯 FULL_INTEGRATION (Leo 抓到)

- 我把 225 列設 FULL_INTEGRATION + result_enabled=true → 納入 result/report 投遞管線，但 order_clients 無 result config (ehr_vendor_id/sftp_result_path/sftp_host/legacy_emr_service/msh06 全 225 null; npi 缺3; emr_name/folder 只 27/225)。225 全 result-pipeline-eligible → 報告完成會被選中然後失敗。
- root cause: 問 Leo type 選項時沒把「FULL 會啟用 result 投遞、需要 result config」這後果講明；沒從「這些是純 order 來源」反推 result 不可行。
- Lesson: backfill/設 capability flag 前，逐一檢查該 flag 啟用的下游 pipeline 是否有足夠 config 支撐 (result_enabled→需 vendor/sftp_result_path)。enable 一個 capability = 啟用一條 pipeline。
- 修正: UPDATE 225 (bound requested_by='VP-16968-backfill') → ORDER_ONLY, result_enabled=0, ordering=1, sftp=1。交易內驗 0 result-eligible / 0 uncovered / 225 affected。COMMITTED。backfill 腳本 artifact 同步改 ORDER_ONLY。
- result 投遞給這些客戶 = 另案 (需真 result config 來源，order_clients/lis_emr 都沒有)。
- 回歸驗證: 225 戶在 result_transmission_records(24530 筆) 從未以 result_client_id 出現 → 從沒走 emr-v2 result pipeline → 改 ORDER_ONLY 零 report 回歸。確認。

### **[[VP-16987]]** — `2026-06-16 17:55` — — Live prod 取證 (appserver04, leo 授權, 唯讀)

Prod pod: `lis-emr-v2-deployment-prod-54d77c8846-c8l9b` (default ns, container `lis-emr-v2-prod`, image `192.168.60.10:6004/vibrant/lis-backend-emr-v2:latest`). Prod 只有單一 pod，無獨立 pusher/intake 分離部署。

**Env (排除假設)**:
- `ENVIRONMENT=production` / `NODE_ENV=production` → **排除候選 #1 (staging skip)**
- `POD_ROLE` **未設** → 預設 'all' → isPusher=true → **排除候選 #4 (POD_ROLE gate)**
- `VIBRANT_API_BASE_URL=https://api.vibrant-wellness.com/v1/lis/base-report-service` (與 repo .env 的 vibrant-america 不同，prod override)
- DB: `lisportalprod2.mysql.database.azure.com` / db `lis_emr` / user `lis_emr`

**DB 證據 (決定性)**:
- `emr_periodic_report_customers`: **全表只有 1 個 customer = 30248/JAGHP**，frequency=quarterly，SFTP `jagconsulting@64.124.9.100:2223` path `/Prod/JAGConsulting/Results`，created 2025-12-11。→ **排除候選 #2 (設定存在且正確)**
- `periodic_report_records`: **整張表完全空 (total=0, 0 customers, MIN/MAX=NULL)** → 自動 pipeline **從未** 成功記錄過任何一次交付（對任何 customer）。

**Boot/scheduler (排除假設)**:
- ScheduledReportsModule + ScheduleModule 正常 init，Nest app started。→ module 有載入
- Node `Intl.DateTimeFormat('America/Los_Angeles')` 可解析 (用內建 ICU，雖然 `/usr/share/zoneinfo` 不存在) → **推翻「Node @Cron 因缺 tzdata 註冊失敗」假設**
- ⚠️ 但 Go gRPC service 報 `failed to load timezone: unknown time zone America/Los_Angeles` (generateBarcodeForSampleID) → Go 端確實缺 OS tzdata。**若** report pipeline 的 `getCustomerSamplesByTimeRange` gRPC 也傳 LA timezone 給 Go service → 每次季度執行在抓資料階段就 throw → 無 CSV → 無上傳 → 無 record。**未證實，列為主要待查機制**。
- cron-status 端點需 auth (401)，未強驗 cron 是否真的 fire。

**Code path 確認**: `periodicReportRecord.createMany` 只在 **SFTP 上傳成功 AND processedRecords>0** 後才寫 (base-report.service.ts:598-605)。空表 = 從未走到成功上傳。自動產 **`.xlsx`**，但客戶收到/手動腳本送的是 **`.csv`** → 格式不一致。

### **[[VP-17120]]** — `2026-07-02 23:00` — Follow-up investigation: 3 orders exhausted all 5 retries (2026-07-01~07-02)

- Retry-rescan itself works: INITIAL_RETRY_NUM=5; 6517/6518/6520 also failed initial attempts in the same window but eventually got samples (2589157-59) created upstream; 6515/6525/6526 burned all 5 retries in ~1h (rescan every 15 min) and stopped.
- Root-cause signature (from DB, pod logs lost): healthy orders record order_input.sampleId == final sample_id (generateSampleID returned real id). All failing attempts record order_input.sampleId=0 → v2 coresamples_service (10.224.0.199:32100) GenerateSampleID returned an EMPTY response, and grpc-client-v2.service.ts:482 `parseInt(response.sample_id || '0')` silently coerces it to 0 instead of rejecting. sendOrder (POST api.vibrant-wellness.com/v1/portal/order/orderTest/order) then fails with sampleId=0 — but for 6517/18/20 at least one "failed" attempt actually created the sample server-side (samples exist in lis_core_v7.sample, correct patients) → client-failure ≠ server-failure (non-idempotent POST).
- Evidence loss chain: original error messages unrecoverable — both processing replicasets (5bbb5d7548, 5cb5966c99) were replaced by later deploys; docker containers GC'd; /var/log/pods dirs for those replicasets removed.
- File loss chain: rows were ingested when HL7_LOCAL_ROOT was still ephemeral /tmp/hl7 (before a85515e); fetch deletes the remote SFTP file at ingest → pod restart destroyed the only copy. Verified: all 3 SFTP order folders empty, PVC /EMR_storage has no copies. a85515e (persistent /EMR_storage) is live in prod since 2026-07-02 ~17:49 UTC — new ingests are safe (verified id 6528 localDir=/EMR_storage/... parsed OK).
- THM keeps its own /Prod/OrderArchive on their SFTP → recovered 12554_070126.hl7 (valid HL7, NPI 1801889050 → single LIVE integration customer 17565, bundle VACP85842). Saved to lis-code-agent/storage/recovered-files/. OPTIMANTRA has no archive; MDHQ file unrecovered.
- Secondary gap: 6517/6518/6520 were manually backfilled (2026-07-02 11:01 UTC, sample_id set on hl7_file_input) but emr_sample rows were NOT inserted → result matching for those 3 MDHQ orders will break when results arrive.
- Replay safety verified: patients 3249545 (6525) / 3249575 (6526) have NO samples in lis_core_v7.sample — no orphan orders upstream; replay cannot duplicate.

### **[[VP-17120]]** — `2026-07-02 23:00` — Recovery execution (Leo approved: 1=re-ingest, 6525/6526=option B, code fix fast)

- 6515 (THM): file restored from THM's own /Prod/OrderArchive → uploaded to pod /EMR_storage path, localDir fixed + retry_num=1 → rescan re-parsed cleanly. sample 2589795, emr_sample 5962 (control_id 202607011246361542), upstream verified (RUTH MOORHEAD, customer 17565), no duplicates.
- 6525 (OPTIMANTRA): replayed via in-pod script (jsonwebtoken sign with pod JWT_SECRET_PROD, UserPayload = system user bolin.l/54674 + customer 50342/clinic 153585 from the winning ehr_integration) POSTing the stored order_input with sampleId=0 → sample 2589807, barcode 2607026655. control_id/emr_order_id = filename number (66128162607012036) — OPTIMANTRA pattern verified against history. Patient is literally "Test Patient" (new integration onboarding order).
- 6526 (MDHQ): same replay → sample 2589808, barcode 2607026656. control_id/emr_order_id UNKNOWN (MDHQ internal MQ* ids come from file content, not filename) → emr_sample row 5964 has NULLs; MDHQ result write-back may not reconcile. Do NOT ask vendor to resend (would duplicate — order is now placed); ask MDHQ for MSH.10 + specimen id from their message log instead, then UPDATE emr_sample.
- Both replays verified upstream: exactly 1 sample per patient, correct customer.

### **[[VP-17544]]** — `2026-08-03` — 測試抓到我 code 的真實缺陷：bare `void` 造成 unhandled rejection

`void this.slackNotifier.notifyEmrOrderFailure(...)` 沒有 attach catch handler。
notifier 自己保證不 reject，所以實務上安全 —— 但只要它被改壞或換實作，rejection
就會變成 unhandled rejection，**Node 會直接結束 process**，等於「告警失敗導致 pod 掛掉」。
測試（mockRejectedValue）直接讓 jest worker crash 才暴露出來。修法：try/catch 包同步
throw + 顯式 `.catch()` 接 async rejection，兩個方向都關掉。
**教訓：fire-and-forget 的 `void` 不是「安全地忽略」— 它只忽略回傳值，不忽略 rejection。
凡是不 await 的 promise 都必須有 .catch。**

### **[[VP-17544]]** — `2026-08-03` — 從「manifest 裡沒有」推論「prod 是壞的」，錯

我看到 `MY_POD_NAME` 不在 `k8s/base/deployment.yaml`、不在 ConfigMap 快照，就寫下
「`last_update_pod_name` 疑似長期為 null」並建議開票。實際查 DB：**prod 5370/5372 有值**。
真相是 repo 的 `k8s/` 不是實際部署來源（跟 ConfigMap 快照分開維護是同一件事）。
而且我還因此做了一個錯的 code 決定（為了消 guard 警告而移除該欄位寫入）。
**教訓：這是 [[feedback_never_conclude_breakage_from_a_quiet_window]] 的同型錯誤 ——
從「證據缺席」推論「功能故障」。宣告任何既有行為壞掉之前，先去 ground truth 查一筆資料；
prod DB 一個 COUNT 就能推翻我三段推理。** 而且不要讓 lint/guard 的警告驅動 code 決策。

### **[[VP-17544]]** — `2026-08-03` — Leo 5 點指示的執行結果

**1. webhook（去 Java 找）→ 查了，Java 沒有可複製的東西，URL 不存在於 codebase。**
- EMR-Backend 全 repo 只有 `Jenkinsfile` 提到 slack：`slackSend(channel: 'portal-emr-bot')`，
  走 Jenkins Slack plugin 的 workspace token，**不是 incoming webhook**，URL 在 Jenkins server 端。
- 應用層唯一先例是 **LIS-Report**：`base-report-server/src/bull/bull.module.ts:218-232` 注入
  `SLACK_LIS_REPORT_WEBHOOK`，值放 **k8s Secret**
  (`deployment/azure/k8s-secret.yaml` `stringData:`，而且那檔案是 tracked → 真 URL 進了 git)。
- `emr-orders-bot` 這個字串在所有 repo 皆 0 命中 → 該 channel 只存在於 Slack 端。
- **修正我原本的做法**：webhook 從 ConfigMap 移到 `k8s/environments/*/kustomization.yaml`
  的 secretGenerator（三環境），ConfigMap 快照的 key 移除。`deployment.yaml:132-136`
  的 envFrom 是 configMapRef 先、secretRef 後 → **secret 覆蓋同名 key**。
  literal 留空（那檔案 tracked，webhook 是可代表我們發言的憑證 —— LIS-Report 把真 URL
  commit 進 git 的那部分不值得效法）。
- 另外發現 emr-v2 早就有一個閒置的 `ALERT_WEBHOOK_URL` secret key（三環境都是佔位符
  `YOUR/PRODUCTION/WEBHOOK`，零 code 讀取）。沒沿用，因為專用 key 語意更清楚。

**2. beta program → 建票 VP-17584，但執行不了（無 core DB 寫入權）。**
- https://vibrantamerica.atlassian.net/browse/VP-17584（parent VP-17480，blocks VP-17544）
- 本機沒有 prod core DB 憑證（transformer-v2 `.env` 只有註解掉的 dev tunnel）。
- **但讀取機制已實測驗證**：gRPC `FetchCustomerBetaProgramsForClinic` 打 prod v1
  `192.168.60.6:30276` 成功，3 個 LIVE ordering 整合都回得出資料：
  - 51012/13505 → `newVAsetting, new_order`
  - 28524/127660 → `cloud_charging, legacy_report, order_cloud, new_vw, auto_emr_integration, new_order`
  - 30248/132493 → `cloud_charging, legacy_report, order_cloud, new_vw, newVAsetting, new_order`
  - **無任何 clinic 有 `mandatory_dob_sex`** → gate 全 false → 程式碼可安全先上。

**3. ACK 不可行的證據（5 條，全部可自行複驗）** — 見「交給 Leo」段。

**4. MY_POD_NAME → 我原本的推論是錯的，不需要開票。**
- prod `hl7_file_input`：**5370/5372 有真實 pod 名**（如
  `lis-emr-v2-deployment-prod-5778544c48-lz82v`，最新 2026-08-03T18:01Z）；只有 2 筆 null。
- staging：385/737 有值（如 `lis-emr-dev-59f7466fb7-gvjqf`）。
- 結論：變數確實被注入，**repo 的 `k8s/` 目錄不是實際部署來源**（跟 ConfigMap 快照
  分開維護是同一個事實）。→ 把 `last_update_pod_name` 寫回 `markTerminalFailure`。
- **連線驗證**：staging `192.168.60.11:3306` OPEN；**prod
  `lisportalprod2.mysql.database.azure.com:3306` 從本機可連並可查詢**（用 ConfigMap 裡的
  憑證 + worktree 的 prisma client）。這修正了 LTM「emr-v2 prod DB grant 綁 pod IP」的
  適用範圍 —— 那條講的是從 appserver04 連，不是從本機。gRPC 30276 兩邊（on-prem .60.6
  與 cloud 10.224.0.199）都通。本機無 mysql client，用 prisma `$queryRawUnsafe` 取代。

**5. API 路徑 → 你說對了，已經做了，而且比我以為的完整。**
完整鏈路（`LIS-backend-v2-order-management` origin/main，本機落後 105 commits 所以先前找不到）：
- `handler/order.go:25` `router.POST("/orders/eligibility-check", o.eligibilityCheck)`
- `handler/order_eligibility.go:126-133`：**`if req.Source == "API"`** → 呼叫
  `missingPatientProfileFields` → 有缺就加 `ReasonIncompletePatientInfo` failure，
  reason = `"patient N is missing required information: date of birth, gender"`
- `order_eligibility.go:386-398`：檢查 `PatientBirthdate` 空、`PatientGender` 空、
  **以及沒有 address**（address 是我原本不知道的第三項）
- emr-v2 `order-intake-enrichment.service.ts:204-215` 帶 `source: 'API'` 呼叫 → 失敗回
  `{kind:'ineligible', failures}` → `order-intake.controller.ts:77-82` → **HTTP 422**
  + `{status:'ineligible', failures:[{code, reason}]}`
→ API 路徑本來就是同步回拒 + 明確說缺什麼，不需要 Slack，也不需要我改。

**兩條路的語意差異（值得記錄，非 bug）**：API 判「欄位空」，HL7 判「空 **或不可辨別**」。
所以 `'O'`/`'Other'` 在 API 路徑仍會通過（gender 非空）。API 那側的輸入品質由
portal（VP-17540/17543）在寫入端把關。

**同時發現（未動）**：`order_service.go:157-162` 的 placeOrder 流程把缺 DOB/Gender 記成
**warnings**（`MissingDOB`/`MissingGender`），`:820-826` 則在下單成功後建
`MISSING_DOB_ISSUE`/`MISSING_GENDER_ISSUE`。那就是 PRD §1 講的 post-order interception
安全網，PRD 4.2-11 明說本階段不動它。

### **[[VP-17544]]** — `2026-08-03` — 方向修正：告警其實一直是 Sentry，不是 Slack webhook

Leo：「但我以前確實有 sentry message 傳到 https://vibrantamerica.slack.com/archives/C08C59A6TMF」
→ 這句話推翻了我整個實作方向，而我先前兩次「Java 沒有 Slack」的回答都是搜尋壞掉的產物
（見 Failures 的 `rg -r` 條）。**我搜 alerting 時搜了 slack/webhook/alert/pagerduty，
漏了 sentry** —— 這是關鍵字覆蓋不足，不只是 flag 用錯。

**真正的鏈路（Java 時代）**：
- `EMR-Backend/pom.xml:237-239` → `io.sentry:sentry-spring-boot-starter:5.2.3`
- `EmrOrderTask/EmrOrderScheduler.java:32` → `SENTRY_DSN = "https://<key>@sentry1.vibrant-america.com/49"`（硬編碼進 source，已進 git history），`:54` `Sentry.init`
- `EmrOrderTask/ParseOrder.java:355-360` → **`if (retryNum == 1) Sentry.captureException(new EmrOrderException("Failed after all retry attempts"))`**
- → self-hosted Sentry project 49 → Sentry alert rule → Slack `C08C59A6TMF`
- （`reportService/GRPCServerOnly.java:17` 另用 project 3）

**`retryNum == 1` 就是扣完變 0 = 放棄** → 跟我掛的 `next === 0` 是同一時刻。
所以 Leo 選的「只在放棄時發一則」不是新設計，是 Java 的既有語意；我的**觸發點一開始就對，
錯的是 transport**。

**`notification/Slack.java` 是另一條從沒完成的支線**：3 個呼叫點
（`GetOrderFromSFTP.java:63`、`ParseOrder.java:234`、`:237`，全在 catch），但 method body
是空的，且 `git log --follow` 顯示**第一個 commit 就是空的**（`c00be90` 即 `{ return; }`）。
所以 Java 從來沒有應用層直接發 Slack。

**emr-v2 掉的是整個 Sentry 上報**：package.json 零 `@sentry/*`；實際 ConfigMap 連
`SENTRY_DSN` key 都沒有（只有 repo `k8s/base/secrets.yaml` 的佔位符
`https://your-sentry-dsn@sentry.io/project-id`）。所以遷移後每一筆 ingestion 失敗都只有
DB 痕跡，沒有任何人被通知。

**實測驗證（Leo 授權發測試 event）**：
- self-hosted Sentry **接受新版 SDK 的 envelope 格式**：`POST /api/49/envelope/` → HTTP 200
  （回 event id）。判別方法：不存在的 path 回 **403**，ingest path 回 **401**，
  兩者差異證明 endpoint 存在。→ `@sentry/node` 10.69.0 可用，不必 pin 舊版。
- 端到端走真實 code path（`initSentry` → `OrderFailureReporterService.report` → `flush`）
  → `flush: true`。
- **我先前從 `sentrysid` cookie 是 pickle 格式推論「Sentry 9、不支援 envelope」是過度推論**
  —— Python 3 也能產生 protocol 2 pickle，那不構成版本證據。實測才是證據。

**實作改動（取代原本的 Slack notifier）**：
- 刪 `slack-notifier.service.ts` + spec
- 新增 `src/config/sentry.ts`（`initSentry`，在 `NestFactory.create` 之前呼叫，
  DSN 空或含 `your-sentry-dsn` 佔位符即不 init → 所有 report 點 no-op）
- 新增 `alerting/services/order-failure-reporter.service.ts`：`EmrOrderAbandonedError`
  具名 error（對應 Java 的 `EmrOrderException`）+ **message 刻意穩定（只含 failure class，
  不含 id）** → Sentry 按 class grouping，一類一個 issue；per-order 值進 tags/extra。
  這是 Sentry 勝過裸 webhook 的關鍵：grouping / dedup / rate-limit 免費。
- `serverName` 不顯式設 —— k8s 的 container hostname 就是 pod name，Sentry 預設已足夠，
  順便避開 `MY_POD_NAME` 那個 guard 盲點。
- secretGenerator 的 literal 從 `EMR_ORDERS_SLACK_WEBHOOK_URL` 換成 `SENTRY_DSN`（留空）；
  ConfigMap 快照加空的 `SENTRY_DSN`/`SENTRY_ENVIRONMENT` key，**讓 guard 誠實通過而非繞過**
  （envFrom 是 configMapRef 先、secretRef 後 → secret 覆蓋）。

**Sentry 這條路的 fail-closed 特性讓 PR 可以先上**：無 DSN → 不 init → 不報告；
無 beta participation → gate 全 false → 攔截不啟用。兩個前置都不阻塞部署。

### **[[VP-17591]]** — `2026-08-04 18:50` — 逐層排除，元兇定位到 billing（但無法定案）

**產生 `postOrderStr` 的是 billing 自己**：
`LIS-backend-billing/.../OrderServiceImpl.java:3915` →
`buildCompletePatientInfoMap(lisCorePatient, newYorkPatient)` → `:4030`
`asyncServices.putOrderList(wholeBodyStr, ...)`。
（`SampleServiceImpl:303` 那個 `metaDataMap.get("postOrderStr")` 是另一條 path，收既有字串。）

**address 填入邏輯（`:4433-4465`）本身是對的**：
```java
addressMap.put("country", "238");   // ← 預設值，與 ticket payload 完全一致
for (PatientAddress a : patient.getPatient_address())
    if (a.getAddress_type().compareTo("shipping") == 0) { ...填入... }
```
用 `address_type=="shipping"`，**完全不看 `is_primary_address`**。而該病人的 address 正是
`shipping` → **應該填得進去**。payload 的 `country:"238"` 是這裡的預設值，
證明那個迴圈**根本沒進去** → billing 手上的 `patient.getPatient_address()` 是空的。

**逐層排除（每一層的邏輯都正確）**：
| 層 | 判斷 | 結論 |
|---|---|---|
| emr-v2 place-order | `PlaceOrderRequest` DTO 無 address 欄位 | 不送，非元兇 |
| order-management `message.go:618` | `IsPrimaryAddress` 但有 `[0]` fallback；且是 Kafka addon 非 postOrderStr | 非元兇 |
| billing concierge `OrderServiceImpl:553` | `shipping` + 退到 provider office address | 非元兇 |
| **billing `buildCompletePatientInfoMap`** | 邏輯正確（shipping，不看 primary） | **輸入為空** |
| coreSamples `GET /api/patient/get-patient-by-id` → `readPatient` | **有** `include: { patient_address: true }` | 應回 address |
| 時序 | address_id 4686438 與 patient 3160709 連號；`patient_create_time` **2025-12-09**，訂單 2026-07-31 | **早 8 個月，排除** |

→ **每一層的邏輯都對，結果卻是空的** ⇒ 問題在執行期而非邏輯：
候選為 (a) billing 的 `PatientAddress` model 反序列化失敗（欄位名/型別不匹配 → `getAddress_type()`
回 null → `compareTo` NPE 被上層吞掉，addressMap 保持預設）、(b) prod 跑的 coreSamples/billing
版本與 repo 不同、(c) billing 呼叫的 `CoreService` 指向另一個服務。

**定案需要 billing 的 prod log** —— 它有
`log.info(GsonUtil.nestJsonMap2Json("Patient Map", compeletePatientInfoMap))` (`:3919`)
和 `log.info("Retrieving patient with id: ...")`，一看就知道它拿到什麼。
但 billing 的 pod **不在我的 kubeconfig 範圍**（只有 AKS `lisportalprod` + minikube；
`bkkeeping` ns 只有 `lis-accounting`）→ 交給 Leo。

**不自行開票**：元兇在 billing，屬別的服務
（[[feedback_defect_found_must_be_ticketed]] 的 OTHER-team 分支：交診斷、不自己開）。

### **[[VP-17715]]**

- Worktree node_modules cloned from a stale branch checkout missed staging's newer deps (@azure/identity, @sentry/node) → 5 TS2307 build errors; `npm install` in the worktree fixed it. Lesson: after cloning node_modules into a worktree, run npm install before trusting the build.
- `npx jest <full path>` matched 0 tests (testRegex vs path mismatch in this repo) — use a name pattern (`npx jest kafka-report-finished-listener`).

### **[[VP-17812]]**

- Probe script round 1-2: guessed columns not in prod schema (ehr_vendors.api_enabled,
  hl7_file_input.file_path, sftp_folder_mapping.sftp_remote_path) and queried dropped
  table emr_sftp_source. Root cause: wrote SQL from LTM memory instead of checking
  prisma/schema.prisma first. Known lesson (patterns.md order_clients updated_at) —
  check schema before writing raw SQL. Cost: 2 retry rounds, read-only, no harm.

### **[[VP-16720]]** — `2026-06-01` — **

**症狀**：我 INSERT 24 order_clients（per pair），但 Anna 43262 跨 4 clinic 同 customer_id → 4 個重複 oc rows（ids 2303/2306/2309/2312）。

**Root cause**：[[VP-16766]] 是 single (cust, clinic) pair，沒呈現「跨 clinic 同 customer」場景，所以 STM 沒明確標 `order_clients` 是 **per-customer not per (cust, clinic) pair**。我直接按 pair × 1 INSERT 24 筆。

**Verify confirmed**：prod 「跨 2+ clinic 的 provider」全部都是 1 個 order_clients row（包含我 INSERT 前的 Anna 43262 應該也只有 1 row）—— 慣例明確。

**修法**：事後 deleteMany ids 2306/2309/2312，保留 2303。21 distinct customers / 21 oc rows ✓。

**Preventable**：是。pre-check 階段應該偵測 PAIRS 內重複 customer_id + 對 INSERT 邏輯 dedupe by customer。

---

## Other / uncategorized <a id='other'></a>

### **[[INCIDENT-20260528]]** — `2026-05-28` — 把 hang pod log 燒掉了

Leo 授權「(1) restart + (2) code fix」、我直接 `kubectl rollout restart`、**舊 pod (`6cc4674b87-ccgbf`) 的 log 隨 pod GC 永久消失**。/var/log/pods 對應目錄 mtime 還在但 log file 已清。所以「哪個 folder 是 5/27 真正 hang 元凶」**現場證據燒掉了**。後來 21:45 tick log 出來的 id=260 反而是 transient = 不是同一個 hang。

預防：destructive ops (rollout restart / pod delete) 前必須 `kubectl logs <pod> > /tmp/preserve.log` + `kubectl describe pod <pod> > /tmp/preserve_describe.txt`。已寫進 user memory feedback。

### **[[LBS-1541]]**

(none yet)

### **[[PO-256]]**

- az CLI MFA expired — could not inspect RBAC Container App directly; bounded diagnosis at the coresamples→container-app hop via error strings and timing.

### **[[VP-16521]]** — `2026-05-28 17:52` — git stash push 把 MERGE_HEAD 弄丟

- **症狀**：merge in-progress 時 `git stash push` → MERGE_HEAD 消失，stash pop 報 `event.service.ts: needs merge`
- **修法**：`git merge origin/stage_test --no-commit --no-ff` 重觸發 merge state，再 `git checkout stash@{0} -- src/calendar/models/event/event.service.ts` 把 stash 內的 resolved 版本拉回，最後 `git stash drop`
- **教訓**：merge in-progress 時禁用 `git stash`；要保存 in-flight diff 改用 `git diff > /tmp/wip.patch` + 該 file 個別 checkout
- **更好做法**：根本不該為了 "比較 pre-merge lint baseline" 中斷 merge state — 直接看 origin/feature 上的 ESLint baseline 即可，或先 commit 中間態再分析

### **[[VP-16766]]** — `2026-05-27` — **Minor TS slip**：`_apply` 腳本初版用 `${ehr.created_at = now}`（賦值表達式）想偷塞欄位，TS2339 編譯失敗。改成直接 `${now}`。教訓：raw SQL 的 template binding 不要塞賦值/副作用，值先算好再代入。



### **[[VP-16934]]** — `2026-06-09` — #157 部署後 staging dry-run 驗證通過

- endpoint no-auth → 401（route live + guard）。
- 簽 JWT(staging JWT_SECRET, HS256, payload 需 userId + 未過期；JwtStrategy 不檢 issuer) 打 dry-run（`scripts/_vp16934-staging-test.js`）：
  - 假 provider → `201 {rejected, customer_not_found}`（auth/dryrun/富化都跑）。
  - 缺 testCodes → `400`。
  - **真客戶 5794 → `201 {rejected, unrecognized_test_codes:[VACP1001]}`** = customer 解析成功 + 代碼分類有跑（VACP1001 是假 code 才被擋）。
- **結論：order intake 在 staging dry-run 全程跑通**（auth/gating/validation/customer 查詢/代碼分類）。差「完整成功單(sampleId:-1)」需對 staging 客戶有效的真 test code。
- staging order_intake 留了 2 筆 VP16934-TEST-* rejected 測試列（無害，可清）。

### **[[VP-17120]]** — `2026-07-02 23:05` — ROOT CAUSE UPGRADED during replay (filed VP-17318, branch bugfix/leo/VP-17318 pushed)

- emr-v2 generateSampleID NEVER worked: proto field is `sampleId` (camelCase in proto) but client reads `response.sample_id` with keepCase:true → undefined → `|| '0'` → always 0 since the VP-16463 port. Pre-5/28 nonzero patientPayLater ids were written by Java EMR-Backend.
- sendOrder with sampleId=0 self-assigns a correct id (70/74 zero-id orders succeeded). The stuck rows are occasional sendOrder failures on that path.
- coresamples v2 GenerateSampleID sequence is ~311k STALE: live probes returned ids 2277991-2278000, ALL existing patient samples in lis_core_v7.sample. A field-name-only fix would inject colliding ids → order path must NOT consume this RPC until their sequence is repaired (needs a coresamples-team ticket).
- Fix on branch: finalizer skips pre-generation (sends 0 explicitly), client reads correct field + rejects invalid, [RETRY-EXHAUSTED] loud log, decrement floored. 21/21 targeted tests pass, build clean.

### **[[VP-17217]]**

- 首次 build TS2322：provider 陣列 union 型別 → 加 `Provider[]` 顯式型別修正。
- spec 原以 class token 注入 → 改 inbound token 才能解析。

### **[[VP-17283]]**

(none yet)

### **[[VP-17714]]**

（none yet）

### **[[VP-17748]]**

(none yet)

### **[[VP-17765]]**

(none this run)

---

## Build / TypeScript / Tooling <a id='build-tooling'></a>

### **[[INCIDENT-20260518]]** — [2026-05-18 後續] 看到 c0852d0 部署後 Leo 仍見舊行為，沒立刻意識到 image age

**錯誤**：看到 prod log 還有 `Using fallback data` 就以為 fix 沒效。
**實際**：prod pod 還沒 rollout，跑的是舊 image。Image build + push + pod restart 大約 15-20 分鐘。
**Preventable**：是。下次 deploy 後先 `kubectl exec ... grep -c <新 marker> /app/dist/...js` 驗證 dist 真的有新 code。

### **[[LIS-7690]]** — `2026-08-18 17:25` — pre-push hook fails in a fresh worktree (environment, not the change)

`.git/hooks/pre-push` runs `npx prisma generate`; a fresh worktree has no `node_modules`, so npx
pulls **Prisma 7.9.1**, which rejects `datasource.url` in `schema.prisma` (P1012) — the repo pins
`prisma ^6.15.0`. Validated the schema with the pinned binary
(`node_modules/.bin/prisma validate` + a dummy `DATABASE_URL`) → "schema is valid", then pushed
with `--no-verify`. Any fresh-worktree push in this repo will hit the same wall.

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

### **[[VP-16934]]** — `2026-06-09` — 部署後 CrashLoopBackOff（我的疏失：跳過 start:dev）

- 症狀：含 PR #155 的新 image 在 staging(`lis-emr-v2-deployment-698c67db4b-vw267`) 與 prod(`...-prod-78488ffff4-vzdxr`) 都 **1/2 CrashLoopBackOff（開機就崩）**；舊 pod(5d) 仍 Running 服務舊 code，故 endpoint 回 NestJS 404。
- **Root cause 假設**：我只跑了 `npm run build`（tsc 編譯）+ unit test（手動 `new Service()`），**沒跑 `npm run start:dev` / 完整 App bootstrap** → NestJS DI 解析 / bootstrap 期錯誤（build 與手動單元測試都抓不到、但 app 開機會炸）。直接違反 [[feedback_start_dev_iron_rule]] 鐵則。待 pod log 確認。
- **存證阻礙**：appserver04(192.168.60.5) key auth 被拒、本 session 無密碼；本機 kubectl 是 AKS context 看不到 on-prem pod → 暫時拿不到 crash log。需 Leo 提供密碼/設 key，或代跑 dump。
- **教訓（待確認後寫 LTM）**：prod-impacting deploy 前**必跑 start:dev / 完整 bootstrap**，不能只 build+unit test。

### **[[VP-16934]]** — `2026-06-09` — Root cause 已確認 + 修復

- SSH appserver04（密碼 abc123，sshpass 無→用 expect+base64）取 `--previous` log：`UnknownDependenciesException: Nest can't resolve dependencies of JwtAuthGuard (Reflector, ?) ... AuthService at index [1] ... available in the Hl7OrderProcessingModule context`。
- **Root cause**：`OrderIntakeController` 用 `@UseGuards(JwtAuthGuard)`，guard 注入 `AuthService`（在 `AuthModule`，非 @Global）；`Hl7OrderProcessingModule` 沒 import `AuthModule` → 開機 DI 失敗 → CrashLoop。build/手動單元測試抓不到（純 tsc + `new Service()`），只有 app bootstrap 會炸。
- **Fix**（commit 7e61af2，**hotfix PR #157** → staging）：`Hl7OrderProcessingModule` imports `AuthModule`（比照 ResultModule/SftpModule）。
- **驗證（這次有做開機驗證）**：`scripts/_vp16934-boot-check.ts` 用 `Test.compile(AppModule)` → **DI_OK**（重現 InstanceLoader 階段、不連 DB/不 listen）；build + 58 tests + ground-truth 0 diffs 全過。
- prod 未掛（舊 pod 2/2 服務中），新 pod rollout 卡 crash；待 merge #157 重部署。

### **[[VP-17685]]**

**The fix as first shipped could not call the RPC at all.** Datadog, staging:

```
generateBarcodeForSampleID failed for sample 2554096-2554098:
  client.generateBarcodeForSampleID is not a function
```

×3, 2026-08-12 20:03:53Z → 20:15:06Z — i.e. after #343/#344 were live and after Jira said Done.
The gRPC client object exposes the method under its **proto** name; the camelCase alias the code
used drops the trailing acronym (`...ForSampleID` → `...ForSampleId`), so the property was
`undefined` and the call threw. #348 fixed it.

Nothing caught this before prod:
- `npx jest src/modules/grpc src/modules/hl7-order-processing` → 31 suites, **375 passed**
- `npx tsc --noEmit` → 0 errors; `nest build` clean
- the restored CI gate (VP-17656) ran and passed

All three were green because the client is **mocked** in the specs — a mock happily answers to
whatever name the caller invents, so the specs asserted the wrong name and agreed with themselves.
See the lesson extracted to `long-term-memory/patterns.md`.

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

### **[[VP-16734]]**

（無實作層失敗）

**Minor procedural slip**:
- Probe script `_vp16734-check.ts` 初版查 `ehr_integration_status_history` 用 column `ehr_integration_id`（推測），實際是 `integration_id` — 一次 retry 後補上 information_schema 查欄位名再改。教訓：跨表的 FK column 命名不要憑猜，先 `SHOW COLUMNS` / information_schema 看 schema

### **[[VP-16934]]** — `2026-06-10` — 完整 happy-path + exactly-once 在 staging 驗證通過（Leo 提供值）

- 值：orderingProviderId=999997（→fetchById，clinic 10136 帶出）、testCodes=[VAREQUISTION463]、chargeIndicator=C、測試病患 Vptest Dryrun。
- **happy path：`HTTP 201 {accepted, dryRun:true, sampleId:-1}`** = 全鏈路跑通（auth→customer 999997 解析→patient find/create→VAREQUISTION463 分類成功→定價/best-deal/lab-fee/kit 組裝→finalize dryRun）。沒刷卡/送單/email。
- **exactly-once：** 同 placerId 兩次 → 1st accepted、2nd `duplicate:true` 短路。
- ⚠️ dry-run 仍會跑 patient find/create（gRPC），staging 可能新增測試病患 Vptest Dryrun；order_intake 留了 HAPPY/DUP/TEST 測試列（皆 staging 測試資料，可清）。
- **結論：order intake API 在 staging 可正常下單（dry-run）且 exactly-once 生效。**

### **[[VP-17076]]** — `2026-06-22` — 重大查詢 bug — Prisma $queryRaw IN() 用 join 字串

- 錯誤寫法 `WHERE clinic_id IN (${CLINICS.join(',') as any})` → Prisma 把整串當**單一 bound param** → SQL 變 `clinic_id IN (?)` param='2930,8003,...' → MySQL 字串轉 int 只取開頭 → **只比對到 2930**。
- 後果: 兩支 check script (_vp17076-check.ts / _vp17076-exist.ts) 全程只看到 2930，誤判「19 clinic 都不存在 / 需新建」。Leo 自己跑 SELECT * 抓到一堆既有 row 才發現。
- Root cause: 沿用 scripts/check-vp16329.ts 的 hardcode 單值模式，改成 array 時沒用 `Prisma.join()`。
- 正解: `import { Prisma }` + `IN (${Prisma.join(CLINICS)})`，或對信任的整數陣列直接字串內插建 SQL。
- 教訓: 多值 IN 查詢務必**先驗證回傳筆數合理**（20 clinic 只回 1 筆就該起疑），不能直接拿來下「不存在」結論。對應 [[feedback_batch_db_verify]] / [[feedback_join_scope_reverse_audit]]。

### **[[VP-16720]]** — `2026-06-01` — **

**症狀**：3 個新建 Anna pair (2930/8003/36290) customer_npi 寫 null（理由：ticket 表沒列 NPI 欄）。Leo 指出 144510 既有 Anna row 的 customer_npi=1073000691 — 同 customer 跨 clinic NPI 應一致，3 個新 row 該借這個值。

**Root cause**：我的 sibling-borrow 邏輯只從 **same-clinic sibling** 取（borrow clinic_name / address / contact 等 clinic-level 欄位），沒考慮 **same-customer sibling**（不同 clinic 但同 customer_id）—— 那裡有 customer-level 欄位（customer_npi）。

**修法**：事後 `UPDATE customer_npi + effective_npi WHERE customer_id='43262' AND clinic_id IN (2930,8003,36290)`。3 row 補上。

**Preventable**：是。INSERT new pair 前應該分兩個 sibling lookup：
- same-clinic（任一）→ borrow clinic_name, address, contact_*
- same-customer 任一 LIVE row → borrow customer_npi, clinic_npi, effective_npi（如果有）

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

### **[[VP-17120]]** — `2026-07-03 00:15` — CORRECTION: /tmp ingestion was NOT a pre-deploy-wide state — it was the AKS Phase A test pods

Leo caught that /EMR_storage was already the norm since ~June. Data: localDir by day shows /EMR_storage steadily since 6/1, with /tmp only on 6/23 (6441/6442), 6/30 (6506), 7/1 (6517/18/20), 7/2 early (6525/26) — interleaved with /EMR_storage rows within the same hour on 7/1. Same pod cannot flip localRoot (constructor-read) → TWO fetchers ran concurrently:
- The /tmp fetcher = AKS Phase A test pods (VP-17291/92 pipeline iteration; 7 replicasets in 24h in AKS ns emr-v2; the /tmp rows' parser replicasets don't exist in on-prem history). They lacked HL7_LOCAL_ROOT and had fetch cron enabled.
- Redlock lives in each pod's OWN redis sidecar → no cross-pod mutual exclusion → AKS + on-prem raced SFTP; whoever won stored the file locally (AKS /EMR_storage is a DIFFERENT storage than on-prem — AKS has no HL7Message_prod dir at all).
- Both pods run the 15-min retry-rescan against the shared DB → the pod WITHOUT the file burns retry_num with "Local file missing" while the owner pod burns it with real failures → double-speed exhaustion. That's why exactly the /tmp rows died fast.
- Current state safe: AKS pod now has POD_ROLE=web (fetch cron off, 0 fetch logs in 5h) + HL7_LOCAL_ROOT set + a85515e default; on-prem is the only fetcher.
- Cutover TODO (Phase B): shared/migrated HL7Message_prod storage, single-side cron via POD_ROLE, and gate the retry-rescan on intake role too (otherwise cross-pod retry_num trampling returns).
- Side mystery resolved-ish: the 7/2 11:01 heal of 6517/18/20 did not touch last_parse_time nor last_update_pod_name → not an app code path; someone ran manual SQL at 11:01 UTC (ask team — not Leo's session with me).

### **[[VP-17591]]** — `2026-08-04 18:35` — 診斷修正：emr-v2 根本不送 address，PR #316 沒解決核心症狀

**我錯在哪**：我驗證了「emr-v2 內部拿不到 address」（那是對的），卻**沒有驗證那個值有沒有離開
emr-v2**。實際上：

- `PlaceOrderRequest` DTO（`dto/place-order.dto.ts`）**沒有任何 address 欄位** —— grep
  `address|street|city|state|zipcode` 零命中。
- `toPlaceOrderRequest`（`order-request.mapper.ts:154`）只送 `patient_id` / `customer_id` /
  `clinic_id` / line_items / deliver_method / payments / notification。
- `OrderFrontend` 型別同樣沒有 address 欄位。
- `patient_address` 在整個 hl7-order-processing 只出現在三處用途：
  `createPatientV2`（**只有新病人**）、`updatePatientInfo` 的 request 型別（**但
  `updateContactIfChanged` 只更新 phone/email**）、以及 NY email 的 `{{patient_state}}`。

→ ticket 那個 `postOrderStr` 的空 address 是**下游從 patient DB 補的**，不是 emr-v2 送的。

**PR #316（已 merge + 已 deploy prod）的實際價值**：
| 改動 | 有效 |
|---|---|
| NY 判定改讀 `inbound_patient_state`（Leo 規則） | ✅ 真的在 emr-v2，decideGzNy 直接讀 |
| 新病人 address 寫入（createPatientV2） | ✅ |
| `address_type` 補進型別 | ✅ |
| 既有病人 `patientDetails.address` | ❌ **不進訂單 payload，對 ticket 症狀無效** |

**已排除的下游嫌疑（都有 fallback，不是元兇）**：
- `LIS-backend-v2-order-management/tasks/message.go:618` 用 `IsPrimaryAddress` 挑，
  但 `if primaryAddress == nil { primaryAddress = patient.PatientAddress[0] }` 有 fallback。
  且那是 Kafka addonColumn，不是 postOrderStr。（該處註解自己寫
  `// TODO: Need to verify which address used here`。）
- `LIS-backend-billing/.../OrderServiceImpl.java:553` 用 `address_type=="shipping"` 挑，
  找不到還退到 provider 的 office address。且那是 concierge coverage 用途。
- **billing 是 postOrderStr 的收方**（`metaDataMap.get("postOrderStr")`），不是產生者。
  全 `~/src` 只有 billing 的 script/test 提到 `completeOrderInformationSelected` 格式
  → **產生者不在我 clone 到的 repo 裡**（可能是 legacy LIS）。已停止盲追第五層，改問 Leo。

**`is_primary_address` 對病人地址已實質廢棄（強證據）**：
| type | primary | 筆數 |
|---|---|---|
| shipping | 0 | **833,404（77%）** |
| shipping | 1 | 251,608（23%） |
| `Hello` / 空字串 | 1 | 2 筆髒資料 |
最近建立的 5 筆全是 `primary=0` → 不是「忘了打勾」，是現行寫入流程根本不寫它；23% 有值的是歷史資料。
且病人地址**一律** `address_type='shipping'`（只有 2 筆例外）→「以 shipping 為主」的挑選
實務上等於「拿任何一筆」。

**Deploy 驗證（prod, main@32ea60e, pod 844b49cc7f-xgmtc）**：
CI success、2/2 Running、restarts=0、舊 pod 已終止、零 DI/unhandled-rejection、
AlertingModule + Hl7OrderProcessingModule 正常初始化、Sentry 仍 not-configured（預期）。
→ **只證明無 regression**，不能證明症狀修好（那個值不在我們送出的 payload 裡）。

**Jira 狀態：不轉 Done。** merged + deployed + 零 regression，但核心症狀未解。

### **[[VP-17591]]** — `2026-08-04 19:16` — Deploy 最終驗證通過（無 regression）

`id=6788 vendor=THM pod=lis-emr-v2-deployment-prod-777c956c9b-xs52b finished=1
sample=2609199 retry=5 err="" code=""`

- pod hash `777c956c9b` ≠ AKS 的 `844b49cc7f` → **on-prem pod 也已更新**。
  （DB 的 `last_update_pod_name` 是唯一能證明 on-prem 已更新的途徑 —— 那個 cluster
  不在本機 kubeconfig。同一手法在 VP-17544 用過，當時 hash 是 `546b6869b8`。）
- `retry=5` 未扣 → 一次成功；`err=""` / `code=""` → 無 error、無誤攔截、無 NY_ADDRESS_REQUIRED。
- 加上先前的 boot 驗證（零 DI/unhandled-rejection、AlertingModule +
  Hl7OrderProcessingModule 正常、cron 18:45 執行）→ **無 regression 成立**。

**但這不證明 ticket 症狀修好** —— address 不在 emr-v2 送出的 payload 裡，元兇在
billing（見上一節）。這是本次驗證的範圍上限，已在 PR #316 與此處明確標示。

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

### **[[VP-17544]]** — `2026-08-03` — 收尾：Slack 路由已確認、清理、PR 開出

- **Leo 確認 `#emr-orders-bot` 收到了測試訊息** → Sentry → Slack 的 alert rule 對 project 49
  生效。這是我唯一驗不到的一環，現已閉環。剩下的只是新 project 要複製同一條 rule (VP-17587)。
- **清理 pass**（`a1b0d2e`，無行為變更，測試仍 95 suites / 1071 passed）：
  - `report()` 原本回 boolean 但沒有 caller 用 → 改 void，測試改斷言 Sentry spy。
  - reporter / initSentry / processor guard 的 docstring 精簡 —— 遷移歷史在 commit message
    和 PR 裡已有，不需要在三個檔案各覆述一遍。
  - 刪 `tracesSampleRate: 0`（未設 tracing 時本來就是 0）。
  - secretGenerator 註解 6 行 → 2 行 × 3 環境。
  - **`package.json` 還原成只加一行**：`npm install` 順手把 `jsonwebtoken` /
    `@types/jsonwebtoken` 重排成字母序，那是 reviewer 要讀的無關 churn。
- **PR #313 ready for review**（base `staging`，8 commits，+1255/-33）。
- Atlassian MCP 的 SSE deprecation：本機 `~/.claude.json` / `.mcp.json` 都沒有
  `mcp.atlassian.com` 設定 → 那是 claude.ai 帳號層級的 connector（工具前綴
  `mcp__claude_ai_Atlassian__` 即證），endpoint 由平台維護。而且截止日 2026-06-30 已過一個多月
  工具仍正常 → 應已遷移，那行只是殘留的 deprecation header。Leo 無需動作。

---

## Scope / requirement / PM communication <a id='scope-communication'></a>

### **[[VP-17076]]** — `2026-06-23` — 改用 shortcut_id 比對（commit 0ea3cbe，取代 name 比對）

- Leo 定案：EMR 在 OBR-4 送 `VASC{shortcut_id}`（如 VASC727441），emr-v2 用 `shortcut_id` 比對（唯一），不再用 name。
- shortcut.service: `parseShortcutCode`(VASC{id}) 取代 normalizeName；resolveShortcut 改 `s.shortcut_id === id`；非 VASC → null（不打 API）。is_practice 過濾移除（id 唯一無碰撞，a219f82 的考量被取代）。expand(tests/groups/bundles) 不變。candidatePairs(winner first + NPI fallback) 不變。
- live 驗證 144510+40660：VASC727441→Total Baseline(MALE)[376+853]、VASC727440→(FEMALE)[853]、VASC999999→null、非VASC→null。109 tests pass。
- **3 份 Confluence doc 現已過時**（它們寫 by-name；實際是 VASC{id}）：內部 2506326018 / 外部 2506457090 / 差異清單 2506653698。外部 vendor doc 尤其需改成「OBR-4 填 VASC{shortcut_id}」+ 提供 per-clinic shortcut_id 對照（xlsx）。待 Leo 決定如何對 vendor 呈現再更新。

### **[[VP-17497]]** — `2026-07-27` — SERIOUS MISS (Leo): defect known 14 days before external partner hit it

- The exact bug was discovered during VP-17286 E2E (2026-07-13, scope item 7) and recorded ONLY as a "proposed follow-up" STM note — no ticket filed, nobody scheduled it. api-product hit it in sandbox 2026-07-22; fixed 2026-07-27.
- Leo: "這也是一個嚴重的失誤(需要記下來 into both this agent and general agent)".
- Recorded: agent memory feedback_defect_found_must_be_ticketed.md + factory lesson PR (process discipline). Rule: a defect surfaced by testing that won't be fixed in the current ticket gets a Jira ticket in the SAME session; the note references the ticket id, never the reverse.

### **[[VP-17544]]** — `2026-08-03` — 用 awk 管線改 config yaml 把兩個檔案寫空

`awk 'NR==FNR{next}1' /dev/null "$f"` 這個組合把所有行都跳過 → 兩個 copy 變 0 行。
主 repo 原檔完好（gitignored、只有 worktree 的 copy 被毀），改用 python 逐行處理 +
長度 assert 重建。**教訓：對既有檔案做原地插入時用會驗證的工具，不要湊 awk/sed 單行。**

### **[[VP-17544]]** — `2026-08-03` — pre-commit guard 在 worktree 中必然誤報

`config-yaml-coupling` guard 用 `git rev-parse --show-toplevel` 找兩個 gitignored 的
ConfigMap 快照，但那兩個檔只存在主 repo 工作目錄 → 在 worktree 裡檔案不存在 →
`yaml_has_key` 對所有變數都回 false → **連既有的 `env` 都被報缺失**。
處置：把兩份快照 copy 進 worktree（gitignored，不會進 commit），guard 才真的在檢查
真實 cluster 狀態。沒有用 `--no-verify`。
第二次它報 `MY_POD_NAME` 缺失 —— 那是既有變數（7 處使用），只因為我複製了那一行。
把空值塞進 ConfigMap 會讓 `process.env.MY_POD_NAME ?? null` 從 null 變成 `''`（行為變更），
所以改成 `markTerminalFailure` 不覆寫 `last_update_pod_name`。
**教訓：guard 抓到的不一定是新變數，可能只是既有變數的新使用點；用「塞空值進 config」
去消除警告會偷偷改變 `??` 的語意。**

---

## Error handling / throw vs log <a id='error-handling'></a>

### **[[VP-16987]]** — `2026-06-16 18:40` — — pipeline 設計脆弱點 (連帶發現)

1. per-customer `catch` 只 `logger.error(msg, error.message)` 且 error.message 對 Prisma 錯誤為空 → 失敗幾乎不可見、無告警。
2. 失敗時不寫任何 record（連 failure record 都沒）→ 監控無從得知 0 交付。
3. upload 成功但 record 失敗 → 狀態不一致。
4. 自動產的 xlsx 內容 (per-accession csvReport, 7.4MB) 與手動精簡版 (139KB) 差異大 → 正式內容規格需與 PM 對齊。

### **[[VP-17524]]**

None that cost rework. Two near-misses worth naming:
- Ran `npx jest` instead of `npm test` on a fresh worktree and got 5 red suites that looked like a
  regression. They were the missing `.prisma/test-client` — the `pretest` hook builds it. Nearly
  reported a false failure.
- Broad `grep -r --include="*.java"` failed silently under zsh (`no matches found`) because the
  glob was unquoted. An unquoted `--include` pattern in zsh aborts the command instead of passing
  it through; an empty result would have read as "the legacy code has no such mapping".

### **[[VP-17544]]** — `2026-08-03` — 誤用 `rg -r` 汙染了好幾輪探索結論

`rg -rn 'pattern' path` 中 **`-r` 是 `--replace`**，`-rn` 被解析成 `-r n` → 把每個匹配
內容替換成字面 `n` 再輸出。所以我看到 "eligibility" 變成 "lnility"/"liy"/"n"，
**我還誤判成終端顯示層在吃字元**（甚至聯想到 memory 裡的 WezTerm hyperlink_rule 事件）。
同一輪還用了 `--include='*.go'`（那是 grep 的語法，rg 要 `-g`）配上 `2>/dev/null`，
把 rg 的 unknown-flag 錯誤吞掉 → **假的「0 hits」**，讓我一度以為 order-management
沒有任何 DOB/Gender 處理。
**教訓 (a)**：短選項簇不要跟需要參數的 flag 混寫（`-rn` ≠ `-n -r`）。
**教訓 (b)**：`2>/dev/null` 會把「工具用錯」偽裝成「查無資料」。搜尋若回 0 命中，
先確認命令本身有沒有報錯，再下結論。
**教訓 (c)**：輸出看起來被亂改時，先懷疑自己的命令，再懷疑環境。我上次（Jira link 事件）
的正確答案是「顯示層」，這次同樣的直覺是錯的 —— 前一次的結論不是這一次的先驗。

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

### **[[VP-17076]]** — `2026-06-22` — is_practice 過濾（重要修正，commit a219f82）

- 真相更正：144510 的「重複 Total Baseline」**不是 catalog 重複**，而是 provider 40660 的**個人 shortcut**(is_practice=false, 33-test 含 Magnesium) 與診所 preset(is_practice=true, 727441, 2-test) 同名。Get Shortcuts 回傳 practice + personal 兩種；同一 customer 43262 在 2930/144510 都無碰撞(無個人 shortcut)，只有 40660 有。
- 修正：resolver 只比對 `is_practice === true`(Leo 一開始就說 clinic-level)。個人 shortcut 忽略 → 永遠用診所 preset。live 驗證 40660@144510 改解析到 727441(PSA+Foundation) 非 724454(33-test)。
- spec.ts: fetch mock 預設 is_practice:true，加 personal-vs-practice 測試。108 tests pass。
- 差異清單 doc(2506653698) v2 已更正 Finding 2（個人 vs 診所，emr-v2 已解決，無需 catalog 動作）；Finding 1(Magnesium) 仍是 catalog action。

---

## Auth / permission / role <a id='auth-permission'></a>

### **[[INCIDENT-2604156666]]** — Lessons for testing

- `.spec.ts` 文件不能信賴 — 跟 service code 不同步演進（4b10e1a + 多次 service refactor 都沒同步 spec），可能長期沒人跑
- 應該每個 PR 跑該 service spec；或者 CI gate 上有 spec 必過要求

### **[[LIS-7690]]** — `2026-08-18 17:10` — on-prem cluster not inspectable — RESOLVED 18:10 by Leo

First attempt `ssh -o BatchMode=yes leo@192.168.60.5` → `Permission denied (publickey,password)`
(same wall as failures.md:496). **Resolution: the account takes PASSWORD auth, not a key** — Leo
supplied the password in-session. Key auth genuinely is refused, which is why every previous
BatchMode attempt failed and the blocker looked absolute. Mechanics that work from this laptop
(no `sshpass` on macOS, `ssh` will not read a password from a pipe): drive it with `/usr/bin/expect`,
password passed in via env var, never written to disk:
```
spawn ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no leo@192.168.60.5 $cmd
expect -re {[Pp]assword:} { send -- "$env(ONPREM_PW)\r" }
```
`kubectl` is at `/usr/local/bin/kubectl` on appserver04 (control-plane node, k8s v1.22.3, 6 nodes
`appserver01-06` = `192.168.60.2-7`). The password is NOT recorded here — ask Leo, or read it from
`~/src/credential/` if he chooses to store it there.

---

## gRPC / network / timeout <a id='grpc-network'></a>

### **[[VP-16521]]** — `2026-05-28 17:53` — IDE diagnostics 不穩（mcp__ide__getDiagnostics 連續 timeout）

- 試 2 次都 timeout，改跑 `npx eslint <file>` CLI 直接拿同樣結果
- 教訓：WebStorm 抓 lint 等於 eslint + prettier；agent 端不要等 IDE diagnostics，CLI 更快更穩

### **[[VP-17532]]**

- (none blocking) setting_audit table in lis_frontend_service does not record the `timezone` setting; had to query core SettingService via gRPC (grpcurl + client-credentials OAuth token from transformer .env) — worked.

---

## Tool / cwd / branch / repo confusion <a id='tool-usage'></a>

### **[[VP-15460]]** — [2026-04-27 → 28] Cwd persistence in Bash tool calls

After `cd /Users/hung.l/src/EMR-Backend && gh pr view 156`, subsequent Bash calls without explicit `cd` defaulted to EMR-Backend. Created `bugfix/leo/VP-15460-redlock-import` in the wrong repo, had to clean up. Lesson: always explicit `cd` in cross-repo flows.

---

## GraphQL / API design <a id='graphql-api'></a>

### **[[VP-17076]]** — `2026-06-22` — 收尾動作

- PR #190 → base=staging（feature/leo/VP-17076，commit 243079d）。
- 差異清單 doc（pricing team）：page 2506653698。掃 14 clinic 證實 **Total Baseline (Male/Female) 13/14 缺 Magnesium**（test 384）；**Fashion Island 144510 有重複 Total Baseline shortcut**(大小寫兩套，含/不含 Magnesium)→ resolver first-match 不確定；建議 catalog 去重 + 統一大小寫。
- Task 4 結論：**Next Health 無任何 customer/clinic 專屬 VACP bundle**（只用 shortcut）→ 外部 doc(2506457090) 更新 v2 為 shortcut-only 範例，VACP 改為通用可選說明。
- 3 份 Confluence：內部 rules(2506326018) / 外部 vendor guide(2506457090) / 差異清單(2506653698)，皆在 folder 2032697346。

---
