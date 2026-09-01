---
id: HL7FAIL-20260729-PLESSEN
type: stm
category: emr_integration
status: blocked-on-other-team
relations:
  unblocked_by: []
  sibling:
  - VP-17537
  - VP-17538
unblock_when: 'BestDeal knows panel 18019 (test: POST /v1/bestdeal/GetBestDealSuggestion
  with bundleId 18019 no longer 400s non_existing_discount_panel_ids); then hl7_file_input
  6735 self-heals via retry-rescan — verify parse_finished=1'
created: 2026-07-29
updated: '2026-07-29'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7-NPI-PRACTICE-MATCH-20260820
- HL7FAIL-20260722-MDHQ
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
- VP-17412
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
- hl7-triage
- bestdeal
- discount-panel
- mdhq
summary: 'hl7_file_input 6735 (Plessen/MDHQ, patient FOGARTY SHANE, VI) stuck parse_finished=0
  no-error-flags: BestDeal 400 non_existing_discount_panel_ids [18019] on every retry.
  Root cause = BestDeal (v1, order team) discount-panel data missing the NEWER official
  bundles: getLegacyBundleMapping HAS 18019 (Foundation Zoomer + Methylation Genetics,
  oldOrderTypeId 415 = discountpanel415) so classify passes, but BestDeal rejects
  18019/18018/17762 while accepting old bundleId 1 -> provisioning gap, not a format
  bug (emr-v2 sends bundleId, 1:1 Java parity). error_detail written (VP-17412 duty).
  Self-heals via retry-rescan once order team adds the panels. NOT ticketed (other
  team scope) — hand-off package given to Leo.'
jira_status: n/a
score: 0.3745
---

# hl7_file_input 6735 — Plessen order stuck on BestDeal panel gap

## Diagnosis chain (2026-07-29)

1. Row: parse_finished=0, retry_num=5, all error flags NULL, order_input NULL -> looked like silent Type C.
2. AKS dead-ends (learned): AKS PV has NO MDHQ order tree; RS 694c74c55 not in AKS -> row owned by ON-PREM prod pod (`lis-emr-v2-deployment-prod` also exists in the internal cluster, ns default). ssh leo@192.168.60.5 now DENIED for key AND password (worked 2026-07-15; creds changed?) — Leo ran the log grep himself on the box.
3. Original HL7 retrieved from MDHQ SFTP remote archive `/plessenhealthcareemr/orders/archive/` (HL7-FETCH archive feature) — file structurally fine: 3 tests incl discountpanel415.
4. On-prem pod logs (via Leo): every attempt fails `POST /v1/bestdeal/GetBestDealSuggestion 400 non_existing_discount_panel_ids:["18019"]` — NOT a parse crash; BullMQ job retries 5x per rescan tick, rescan re-enqueues (job seen 5h after receipt) => will SELF-COMPLETE once data fixed.
5. Contrast probes (prod pod, ORDER_API_TOKEN Bearer): getLegacyBundleMapping HAS 18019 (oldOrderTypeId 415, official, $700; response is an OBJECT keyed by bundleId, ~1.6MB). BestDeal: bundleId '1' -> 200 OK; '18019','18018','17762' -> 400; '415','414' (oldOrderTypeId form) -> 400. => BestDeal's discount-panel universe lacks the newer official bundles; emr-v2 request format is correct (parser sends bundle.bundleId, Java line 834-838 parity).

## Actions taken

- error_detail written on row 6735 (VP-17412 agent duty, 1 row bounded UPDATE).
- NO ticket filed — BestDeal is the order team's v1 service (scope boundary rule); hand-off package in the session report for Leo.

## Ops notes

- getLegacyBundleMapping auth: token must be sent WITH `Bearer ` prefix (raw ORDER_API_TOKEN alone -> 401 "invalid number of segments"); response shape = object keyed by bundleId, not array.
- MDHQ vendor SFTP: 34.199.194.51:2210 user vibrantamerica (ehr_vendors 'MDHQ(Cerbo)'); order archive at <practice>/orders/archive/.
- Blast radius: ANY EMR order carrying a newer discountpanel code will strand the same way (silent stuck row; only pod logs / error_detail show why). Watch for more rows if practices adopt Foundation Zoomer + Methylation Genetics before the BestDeal fix.

## [2026-07-29 23:20Z] RESOLVED — order placed as sample 2605735

- Deploy race: #299 (bounded retry) reached prod BEFORE #301 (substitution) — the 21:46Z rescan burned retry_num 5->0 with the old BestDeal call (last_error captured it; VP-17533 worked day one). retry_num=0 => rescan stopped.
- Recovery: bumped retry_num=3 (whitelisted flip) but the owning rescan never ticked for 90min; re-drove MANUALLY: staged the archived HL7 onto the AKS prod PV (path from row.localDir) + enqueued BullMQ job (Queue 'process-hl7-file', jobId hl7-6735-manual-vp17535, pod redis sidecar localhost:6379). Job completed: parse_finished=1, sample_id=2605735, total $1300, order items include 853+851 (substitution PROVEN in prod).
- Jenkins tag/checkout skew CONFIRMED both directions: pod image tagged bacfb1c (#300) contained #301's code — Jenkins tags with the triggering commit but builds the branch HEAD at build time. Image tag is NOT a version proof; only dist content is.
- REMAINING: customerPay $1300 charge FAILED — stripe 'PaymentMethod pm_1TFctl... does not belong to Customer cus_UvXe...' = VP-17411 class, SAME practice (Plessen 150325) as unpaid 6390/6502/6504. Order shipped unpaid per HL7 semantics; payment recovery joins the VP-17411 queue (charging-team stripe fix dependency). error_detail + last_error updated on the row.
- Code nit noted (Leo to decide): the success path does not clear last_error — a placed row can carry a stale failure text (cosmetically fixed by hand for 6735; one-liner if wanted).

## Pending

- INTERIM SHIPPED (Leo, 2026-07-29, 2nd rework): VP-17535 / PR #301 draft (e5c5ec2) — six unprovisioned Zoomer+Genetics panels are SPLIT INTO COMPONENT TEST IDS inside the single BestDeal request (18006=842+843, 18015=844+724, 18016=823+822, 18017=854+822, 18018=849+856, 18019=853+851; dedupe for shared 822/already-ordered components); response passes through untouched = LIVE pricing, nothing hardcoded (Leo: hardcoded prices break as prices change — his first synthetic-response spec was itself a live BestDeal answer for [853,851]). Verified vs prod BestDeal: [853,851] 200 $700, [844,724] 200. REMOVE when BestDeal 200s for 18019; VP-17535 stays open as removal tracker.
- Order team: add/enable the newer official bundles (at least 18019; likely the whole recent batch incl 18018/17762) in BestDeal's discount-panel data.
- After fix: confirm 6735 self-completes on a rescan tick (sample_id populated); if rescan stopped, re-drive manually (local file retained on-prem).
- DONE (Leo approved 2026-07-29): hardening shipped as VP-17533 / PR #299 draft — hl7_file_input.last_error column (ALTER applied+verified staging+prod) + catch-all routing uncaught parse throws through markFailure (bounded retry, bare-fact trace). After deploy, 6735 self-documents its BestDeal 400 and counts down to triage visibility.
