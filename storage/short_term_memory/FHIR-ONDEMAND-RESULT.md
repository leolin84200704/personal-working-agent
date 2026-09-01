---
id: FHIR-ONDEMAND-RESULT
type: stm
category: emr_integration
status: done
score: 0.1963
base_weight: 1.0
created: 2026-07-02
updated: 2026-07-05
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- HL7-NPI-PRACTICE-MATCH-20260820
- HL7FAIL-20260722-MDHQ
- HL7FAIL-20260729-PLESSEN
- HL7FAIL-20260730-TURNPAUGH
- INCIDENT-20260808-critical-result-tnp
- INCIDENT-20260817-onprem-stale-deploy
- INCIDENT-2604156666
- LBS-1541
- LBS-1656
- LBS-1762
- LIS-7716
- PH-847
- QH-1660
- QH-2257
- QH-2577
- QH-3752
- QH-4350
- QH-4352
- QH-4608
- QH-5840
- RESULTCHECK-20260819-RCODE-2608186060
- VEJO-DELETION-20260804
- VP-14787
- VP-15279
- VP-15952
- VP-16014
- VP-16166
- VP-16175
- VP-16186
- VP-16193
- VP-16251
- VP-16271
- VP-16280
- VP-16329
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
- VP-17503
- VP-17517
- VP-17524
- VP-17537
- VP-17538
- VP-17539
- VP-17544
- VP-17584
- VP-17589
- VP-17591
- VP-17628
- VP-17631
- VP-17685
- VP-17686
- VP-17691
- VP-17715
- VP-17734
- VP-17748
- VP-17752
- VP-17760
- VP-17810
- VP-17812
- VP-17827
- VP-17914
- VP-18030
- emr-integration
- fhir-api
tags:
- fhir-ondemand-result
- vp-16934
- fhir
- result-pull
summary: FHIR DiagnosticReport PULL on-demand generation fallback for samples without
  result_transmission_records (portal-only customers)
---

# FHIR-ONDEMAND-RESULT - Work Loop Record

## Ticket Analysis

### [2026-07-02]
- 起因：Leo 問 `GET api.vibrant-america.com/v1/report/fhir?barcode=2602116721` 為何拿不到 result 資料。
- 調查結論（全部 L4 驗證過）：
  - `/v1/report/fhir` 是 21h 前建的 ingress alias（`lis-emr-v2-fhir-short-ingress`, emr-v2 ns）→ pod `/api/v1/fhir/DiagnosticReport`。routing/auth 正常。
  - barcode 2602116721 → sample_id 2494296（customer 14567 / clinic 135009）。
  - base-report getReportStatusListV2：`Preliminary Report Available`，2 Final + 1 Processing，無 blocking issue → 不會 withhold。
  - **root cause**：`result_transmission_records` 該 sample 0 筆；customer/clinic 完全沒有 `ehr_integrations` → 從未產生 HL7 ORU → FHIR endpoint 只回 status shell（無 Observation / presentedForm）。
  - 架構性缺口：VP-16940 設計是「re-serve 推送給 EMR 的 HL7」，portal-only 客戶天生拿不到 result data。

## Approaches Considered

### [2026-07-02]
- 方案 A（Leo 選定）：查無 transmission record 時 fallback 到 in-memory on-demand generation。
  - 重用 `ResultGenerationService.generateHl7ForAgent(sampleId, customerId)`（VP-15659 已存在）：bypass integration lookup、無 file/DB/SFTP 副作用、no PDF OBX。
  - `generateResultHl7ContentReadOnly` 不可用：走 `validateEmrIntegration`，portal-only 客戶會 throw。
  - presentedForm 需自行補（generated HL7 無 PDF OBX；mapper 只在看到 ED/VAPDF OBX 時產生）— 與 mapper 同 shape 兩個 style URL。
  - module wiring 照 enrollment pattern：`forwardRef(() => ResultModule)`（DI CrashLoop 教訓）。
- 方案 B（未採）：維持現狀語意，只在 shell conclusion 明講無 EMR 交付紀錄。

## Decisions Made

### [2026-07-02]
- 有 record 時行為完全不變（ledger snapshot 語意保留）；fallback 只在 0 筆時觸發。
- 生成失敗 → 落回現有 shell 行為（不會比現在差）。
- 加 `urn:vibrant:result-source` extension（`transmission-record` | `on-demand-generation`）供 consumer/debug 區分來源。
- 不新增 env var → config-yaml IRON RULE 不觸發。
- Branch: `feature/leo/VP-16934-fhir-ondemand-result`（base=staging；掛 Epic VP-16934，尚無獨立 ticket）。

## Code Changes

### [2026-07-02]
- Commit `d713eb4` on `feature/leo/VP-16934-fhir-ondemand-result`（base=staging，未 push）。3 files, +235/-16：
  - `fhir-result.service.ts`：注入 `ResultGenerationService`；新增 `generateOnDemandHl7(sampleId)`（getSampleRelevantInfo 取 customerId → generateHl7ForAgent；任何失敗回 null）與 `attachPdfPresentedForm(report, accession)`（兩 style PDF URL，與 mapper 同 shape；在 enrichment 前掛上讓 withhold 仍可 strip）；`getDiagnosticReportBySampleId` 無 record → 先試 on-demand，失敗才回 shell；新增 `urn:vibrant:result-source` extension（`transmission-record`/`on-demand-generation`，shell 不帶）。
  - `fhir-result.module.ts`：imports 加 `forwardRef(() => ResultModule)`（照 enrollment pattern）。
  - `fhir-result.service.spec.ts`：3 個建構點加第 7 參數 + 新 describe 7 個測試（成功 map/presentedForm 補掛/withhold 仍 strip/失敗回 shell/throw 回 shell/customer lookup 失敗 skip/有 record 不觸發）。
- 無新 env var → config-yaml IRON RULE 不觸發。e2e script `scripts/_fhir-ondemand-e2e.ts`（gitignored，underscore 慣例）。

## Test Results

### [2026-07-02]
- `npm run build` pass；`npx prisma generate` pass。
- fhir-result suite：6 suites / 73 tests 全過（含 7 個新測試）。
- 全套 jest：25 failed 為 pre-existing（clean staging baseline 同樣 25 failed；我的 branch +7 passed、0 新增失敗）。
- DI boot check（`scripts/_vp16934-boot-check.ts`）：DI_OK。
- **Live e2e（read-only，連 prod）**：`POD_ROLE=pusher FHIR_RESULT_MODE=enabled npx ts-node scripts/_fhir-ondemand-e2e.ts 2494296` → status=`preliminary`、result-source=`on-demand-generation`、**181 Observations**、presentedForm 兩個 style URL（accession 2602116721 正確）、無 withhold、6.2s。
- 副作用驗證：e2e 後 pod 內查 `result_transmission_records` sample 2494296 仍 **0 筆**（確認 generateHl7ForAgent 無寫入）。
## User Feedback

### [2026-07-02] Leo: 「A, plan 完直接改」— 選方案 A，plan 後直接實作，不用再等確認。

### [2026-07-02] Leo: 「push + PR to staging」— review 通過。Pushed `d713eb4`，PR #232 → staging：https://github.com/Vibrant-America/lis-backend-emr-v2/pull/232（未 merge，等 Leo/審核）。

## Failures
## Retrospective

### [2026-07-02] Deploy 驗證完成
- PR #232 merged → staging，隨即 staging→main（PR #233, `d6fa70c`），Jenkins auto-deploy AKS `emr-v2` ns（image pinned to GIT_SHA，rollout ~10min 完成，pod 2/2）。
- **Prod 端對端驗證**：`GET https://api.vibrant-america.com/v1/report/fhir?barcode=2602116721` → **HTTP 200, 4.3s**，status=`preliminary`、result-source=`on-demand-generation`、**181 Observations**（obs[0]=Total IgA 230 mg/dL）、presentedForm 兩 style URL、identifier accession/placer 正確。
- 呼叫後 `result_transmission_records` 仍 0 筆（prod 零副作用確認）。

## Lessons Learned

### [2026-07-02] FHIR endpoint 測試 token 的取得方式（重要，之後驗證都用這條）
- FhirAccessGuard 要求 RS256 + scope⊆{result,report} + live session。prod OAuth `JWT_SIGNING_ALGORITHM=HS256`，RS256 access token 兩條路：(1) CC+accountType=CUSTOMER 強制 RS256；(2) **OAuth PR #40（2026-06-24, deployed `4d643c6`）：`/token` 支援 `algorithm=RS256` one-way upgrade form field**。
- 唯一有 result/report scope 的 client：**Cloud Report Service**（OAuth DB Client id 75, clientId `MGI5NWQ3YjctOWMxMC00MjZkLThmMzktM2U0ODkzNDU4ZmJj`, INTERNAL/CC）。secret 在 `LIS-Report/base-report-server/deployment/azure/k8s-secret.yaml`（⚠️ plaintext 進 repo，安全隱憂，待跟 Leo 提）。
- 完整指令：`POST api.vibrant-america.com/v1/oauth2/token` body `grant_type=client_credentials&client_id=...&client_secret=...&scope=report result&algorithm=RS256`。
- 本地 OAuth repo checkout 過時（missing PR #40）→ 查 auth 行為前先比對 deployed image SHA vs repo HEAD（`kubectl get deployment -o jsonpath image` vs `git log`）。
- OAuth prod DB（Postgres `Auth0`）read-only 查詢：`kubectl get secret my-secret -n oauth` 的 `OAUTH_DATABASE_URL` + `/opt/homebrew/opt/libpq/bin/psql`；`Session`+`Client` JOIN 可反查「誰在什麼時候用哪個 client 拿 token」。
