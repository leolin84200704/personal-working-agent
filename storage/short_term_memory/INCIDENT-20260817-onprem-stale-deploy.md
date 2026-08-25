---
id: INCIDENT-20260817-onprem-stale-deploy
title: emr-v2 on-prem prod pod has run Aug-4 code for 13 days — manual result repush
  for cust 4953 dies on Prisma enum PER_REPORT_GROUP
status: resolved
category: emr_integration
created: 2026-08-17
updated: '2026-08-19'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7-NPI-PRACTICE-MATCH-20260820
- HL7FAIL-20260722-MDHQ
- HL7FAIL-20260729-PLESSEN
- HL7FAIL-20260730-TURNPAUGH
- INCIDENT-20260808-critical-result-tnp
- INCIDENT-20260817-onprem-deploy-freeze
- INCIDENT-2604156666
- LBS-1541
- LBS-1656
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
- VP-16685
- VP-16734
- VP-16765
- VP-16766
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
- VP-17312
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
- VP-17810
- VP-17812
- VP-17827
- emr-integration
- fhir-api
tags:
- incident
- deploy-drift
- on-prem
- result-push
- prisma-enum
- vp-17715
summary: 'Leo''s manual result publish for samples 2602947/2602948 (cust 4953 MDHQ)
  failed with "Value ''PER_REPORT_GROUP'' not found in enum ''ResultPushLevel''".
  Root cause is NOT the VP-17715 work: prod DB + AKS cloud pod are correct. The on-prem
  prod pod (lis-emr-v2-deployment-prod, replicas=1, appserver04) has process uptime
  13.15 days = started 2026-08-04 18:28Z, so its baked Prisma client predates the
  2026-08-14 enum. Every main merge since 2026-08-04 11:14 PDT is absent from on-prem,
  which still OWNS 536 of 1036 LIVE result-enabled integrations.'
score: 0.8856
---

# INCIDENT-20260817 — emr-v2 on-prem prod deploy drift (13 days)

## Trigger

### [2026-08-17 22:05Z]
Leo published a report; the API returned:
```
Invalid `prisma.ehrIntegration.findFirst()` invocation:
Value 'PER_REPORT_GROUP' not found in enum 'ResultPushLevel'
  at ResultGenerationService.getIntegrationDataById (/app/dist/.../result-generation.service.js:538)
  ... ResultService.generateResultHl7 (REST POST /api/v1/result/generate/:sampleId)
```
sample_id 2602947 (and a second attempt 2602948 at 22:06Z).

## Diagnosis (all against prod ground truth)

- **Prod DB is correct**: `SHOW COLUMNS ehr_integrations.result_push_level` =
  `enum('WHOLE_ORDER','PER_REPORT','PER_SAMPLE_TYPE','PER_REPORT_GROUP')`. Exactly one
  LIVE row uses PER_REPORT_GROUP: `c0000CMYCWWC500T2I1A85BHS` (cust 4953 / clinic 5492,
  MDHQ, `/rcode/results/`, `deferred_report_short_names=["GUT5"]`, **pipeline_location=cloud**).
- **Both failing samples belong to cust 4953** — `result_transmission_records`
  `cmrzjecp4001jxo07e6l8x9le` (sample 2602947) and `cmrzid8jw001dxo07zd51fn68` (2602948),
  both created 2026-07-24, `generation_status` flipped to GENERATION_ERROR with
  `updated_at` 22:05:21Z / 22:06:01Z today. Blast radius so far = these 2 rows only
  (`error_message LIKE '%PER_REPORT_GROUP%'` returns exactly 2 rows fleet-wide).
- **AKS cloud prod pod is NOT the failing server** (positive control):
  `lis-emr-v2-deployment-prod-857f97665f-qts77`, image
  `lisportalprod.azurecr.io/lis-backend-emr-v2:52282e3f…` == origin/main HEAD `52282e3`;
  `PER_REPORT_GROUP` present in `/app/node_modules/.prisma/client/`, `GROUP:MAIN` present
  in dist. Its logs for the last 3h contain zero `PER_REPORT_GROUP` and no reference to
  either sample.
- **On-prem prod pod is the failing server**: `GET http://192.168.60.5:31318/api/v1/health`
  (NodePort of on-prem `lis-emr-v2-deployment-prod`, `replicas: 1`, nodeName appserver04)
  reports `uptime: 1136685s` = **13.15 days → process start 2026-08-04 18:28:51Z**
  (= 11:28 PDT, right after main merge `32ea60e` 11:14 PDT). The image is
  `192.168.60.10:6004/vibrant/lis-backend-emr-v2:latest`, `imagePullPolicy: Always`, and
  the Prisma client is baked at image build → a process started 2026-08-04 cannot know an
  enum value added 2026-08-14.
- **The image itself is fine**: on-prem registry `latest` digest
  `sha256:d75f4ed3…` == tag `52282e3f978d63e1828d9d5c77d7b2305a510f28`. So the Jenkins
  build+push stage ran; the on-prem `kubectl rollout restart` half never took effect
  (a failed/never-run deploy branch, or a new pod that never became ready so the old
  ReplicaSet kept serving). **Not yet confirmed — needs on-prem kubectl (SSH creds).**
- **on-prem staging pod is healthy/current** (`:31320` uptime 46020s = 12.8h, staging
  builds do restart it) → the breakage is specific to the main-branch on-prem prod path.

## Drift scope (what is live on-prem vs main)

On-prem prod runs main as of `32ea60e` (2026-08-04 11:14 PDT). Missing since then:
VP-17595 (dead on-prem Kafka fallback removal), VP-17589 (clinic promo), VP-17503
(whole-order PDF fail-loud), **VP-17524 (OUT_OF_ reference-range → correct HL7 status;
the TNP class of defect)**, VP-17631 (OBR panel labels), VP-17685/17686/17687/17691,
PH-850/851/853/855/860/861, VP-17715.

`ehr_integrations` LIVE + result-capable by owner: **cloud 500 / onprem 536** — the stale
pod still owns the majority of automatic result generation. Fleet transmission health is
green (7-day daily counts all TRANSMITTED, 1 unrelated gen error on 08-13), so the drift is
silent: it withholds fixes rather than breaking delivery.

**Lesson (candidate for LTM):** "deployed to prod" for emr-v2 requires verifying BOTH
prod pods. Every STM since 2026-08-04 that claims a fix is live on prod verified only the
AKS pod (image SHA + dist string) — the on-prem pod's process uptime was never checked.
Cheap 2nd signal that needs no cluster access: `curl :31318/api/v1/health` → `uptime`.

## Immediate options for the 2 blocked reports (cust 4953, cloud-owned)

1. Re-issue the same `POST /api/v1/result/generate/{2602947,2602948}` against the **AKS
   cloud pod** (correct owner for a `pipeline_location=cloud` integration, has the enum).
   Needs the admin JWT (HS256 via `JWT_SECRET`, or Leo's existing token) + port-forward or
   the internal service. No deploy, no drift exposure.
2. `kubectl rollout restart deployment/lis-emr-v2-deployment-prod` on-prem — fixes the
   root cause but simultaneously deploys 13 days / ~10 PRs to the 536 on-prem-owned
   integrations. Prod-change gate + Leo go required.

## Action taken — option 1 executed (Leo go: "both, reports first")

### [2026-08-17 22:21Z] Repush re-issued on the AKS cloud pod — DELIVERED
Ran inside `lis-emr-v2-deployment-prod-857f97665f-qts77` (`/tmp/repush.js`): minted a
15-min HS256 admin token from the pod's own `JWT_SECRET` (`userId 999997`,
`internal_user_role=admin`) and POSTed `/api/v1/result/generate/{sample}` with
`send_result: true` — the identical call that failed on the on-prem pod. Both HTTP 201:

| sample | new record | file | bytes | gen ms | TRANSMITTED |
|---|---|---|---|---|---|
| 2602947 | `cmsxst1f5000fxa07117b3819` | 2607246450.hl7 | 5,145,651 | 33,145 | 22:22:20Z |
| 2602948 | `cmsxsuhym000hxa07hkate4pr` | 2607246451.hl7 | 3,972,875 | 23,635 | 22:23:13Z |

DB: both GENERATED / ENCODED / TRANSMITTED, `error_category` null,
`sftp_remote_path=/rcode/results/<file>`, `integration_request_id` = the real 4953 row.
Reverse audit on cust 4953 for the whole 22:00Z+ window returns exactly these 2 new rows
plus the 2 old GENERATION_ERROR rows from Leo's attempt (left as evidence, untouched).

**Peer-side verified** (channel-liveness rule — our own upload log is not proof):
connected read-only to MDHQ SFTP `34.199.194.51:2210` user `vibrantamerica`, listed
`/rcode/results/` → `2607246450.hl7` 5,145,651 B mtime 22:22:16Z and `2607246451.hl7`
3,972,875 B mtime 22:23:10Z. Byte sizes match the DB rows exactly.

## Open items
1. Confirm on-prem ReplicaSet/rollout state and why the restart never landed (needs
   `ssh leo@192.168.60.5` password) — preserve `kubectl describe`/events BEFORE any restart.
2. Decide 1 vs 2 above for the two reports Leo wants out.
3. Ask Leo which URL/token the publish tool used (confirms the on-prem attribution from
   the client side).
4. After the on-prem redeploy: re-verify the VP-17524 / VP-17503 / VP-17591 behaviours on
   an on-prem-owned integration — they have never actually run in prod.

> **同一事故的另一面**：`INCIDENT-20260817-onprem-deploy-freeze` — 根本原因（Kafka guard + 無 Azure identity + maxUnavailable 0）。兩份刻意不合併：一份記症狀與補救，一份記機制。

### [2026-08-18] 漂移已解除 — on-prem prod pod 於 18:33Z 重新部署

VP-17734 的 session 在 22:15Z 實打 on-prem prod pod（`POST :31318/api/v1/result/generate/2590476`,
HTTP 201），當時 uptime 13,251s → **process start 2026-08-18 18:33Z**，就在 emr-v2 PR #376
（`staging`→`main`，18:19:36Z）合併之後。13 天的 deploy drift 到此結束，該次 repush 全程正常
（GENERATED/ENCODED/TRANSMITTED + peer-side SFTP 對帳）。

**仍未結案**：
1. 為什麼 08-04~08-17 期間 rollout 沒生效，事後沒有取證（pod 已被換掉，`kubectl describe`/events
   永久消失）—— 「Preserve evidence before restart」這條這次沒做到。
2. VP-17524 / VP-17503 / VP-17591 的行為在 on-prem 路徑上**從來沒有真的跑過**，
   redeploy 之後才第一次上線；三份 STM 已加 RE-CHECK 註記（2026-08-18 dream）。
3. **GitHub Actions 的綠燈只證明 AKS cloud 那條路。** emr-v2 的 on-prem 由 Jenkins 部署，
   `Push on main` success 對 on-prem 一無所知。要第二個訊號：`curl :31318/api/v1/health` 讀 `uptime`
   （不需要 cluster 權限；本機不在 VPN 上時會 curl exit 7，那是「測不到」不是「掛了」）。

### [2026-08-19] RESOLVED（dream 判定）

Drift 已於 2026-08-18 18:33Z 結束並經雙重 live 驗證（本檔 22:15Z repush round-trip +
LIS-7690 的 uptime parity probe：on-prem 19,028s ≈ AKS 19,047s，同一 Jenkins run 重啟）。
殘留事項各有去處：取證損失是永久的（教訓已記）；`:latest` 未 pin 記在 repos.md 與 LIS-7690；
Key Vault 遷移 = VP-17756。本檔標 resolved。
