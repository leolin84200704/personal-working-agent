---
id: INCIDENT-20260808-critical-result-tnp
type: stm
category: emr_integration
status: active
score: 0.9415
base_weight: 1.0
created: 2026-08-08
updated: '2026-08-14'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7-NPI-PRACTICE-MATCH-20260820
- HL7FAIL-20260722-MDHQ
- HL7FAIL-20260729-PLESSEN
- HL7FAIL-20260730-TURNPAUGH
- INCIDENT-20260817-onprem-stale-deploy
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
- emr-integration
- fhir-api
relations:
  unblocked_by: []
  blocks: []
  sibling:
  - VP-17524
unblock_when: ''
tags:
- incident
- result-content
- patient-safety
- hl7
- reference-range
summary: Critical-high/low reference range types have no arm in emr-v2's mapReferenceTypeToStatus
  switch, so they fall through to RESULT_UNKNOWN_ERROR and are delivered to EMRs as
  TNP ("Test was not done due to an error") instead of HH/LL. Pre-existing; made visible
  by VP-17524's loud default. Found by dream closeout scan 2026-08-08. NOT yet ticketed
  — awaiting Leo.
jira_status: none
---

# INCIDENT-20260808 — critical results delivered to EMR as TNP

## Discovery

Found during the 2026-08-08 dream closeout audit while scanning prod pod health for
VP-17628's deploy. Not related to VP-17628 — incidental find in the same log window.

Prod pod `lis-emr-v2-deployment-prod-5f47cb8554-4wjk2` (image `dfe5109` = PR #334 merge),
32h log window: 9 `level:error` lines, of which 2 are this defect.

## What happens

`ResultStatusMapperService.mapReferenceTypeToStatus()` (src/modules/hl7/services/result-status-mapper.service.ts)
normalizes the gRPC reference range type then runs an enumerated `switch`. The switch has arms for:

- `RESULT_NORMAL`, `RESULT_BORDERLINE`, `RESULT_HIGH_MODERATE_ABNORMAL`,
  `RESULT_LOW_MODERATE_ABNORMAL`, `RESULT_LOW_ABNORMAL`, `RESULT_HIGH_ABNORMAL`, `RESULT_ABNORMAL`

There is **no arm for `RESULT_HIGH_CRITICAL` / `RESULT_LOW_CRITICAL`**, so they hit
`default:` → `RESULT_UNKNOWN_ERROR` → description `"Error in fetching results for the sample!"`
→ abnormal flag **`TNP`**.

The irony: the downstream tables already fully support criticals —
`isSampleTestStatus()` lists `RESULT_HIGHER_CRITCAL` / `RESULT_LOWER_CRITCAL` (legacy Java typo,
preserved), `getStatusDescription()` maps them to `Critical! Higher range` / `Critical! Lower range`,
and `getAbnormalFlagFromDescription()` maps those to **`HH`** / **`LL`**. Only the one
`mapReferenceTypeToStatus` arm is missing, so the flags can never be reached from a
reference-range-typed input.

## Proven impact (prod, delivered)

**Sample 2607611** — 2026-08-07T22:25:16Z, customer 18879, vendor **MDHQ**, `send_result=true`:
- Test 23 (`GLUCO`, Glucose): `rawResult=467`, reference range `70-100`, gRPC
  `resultStatus="RESULT_HIGH_CRITICAL_M"`.
- Mapped: `RESULT_HIGH_CRITICAL_M → RESULT_UNKNOWN_ERROR → "Error in fetching results for the sample!" → TNP`.
- Delivery: `marked GENERATED` → `SFTP upload success=true` → `Successfully generated and
  transmitted HL7 result` (record `cmsjijho3000hxm07ifd5x531`, file `2608036159.hl7`).

So a **critically high glucose (467 mg/dL) physically reached the customer's EMR flagged as
"test not processed"** rather than `HH`. Per the VP-17524 note, `RESULT_UNKNOWN_ERROR` renders as a
blanked OBX-8 plus an `NTE|...|Test Not Processed` segment — the clinician sees "not done", not a
critical value.

**Sample 2611152** — 2026-08-08T14:10:39Z, same customer 18879/MDHQ, also transmitted
(`2608066131.hl7`). Unknown type here is `RANGE_ERROR` (a distinct, separate gap — TNP may
actually be defensible for this one; needs a product call, unlike the criticals).

## Root cause classification

**Pre-existing, not a VP-17524 regression.** `git log -S "RESULT_HIGH_CRITICAL"` on
`src/modules/hl7/services/result-status-mapper.service.ts` returns **nothing** — the string has
never existed in the file. VP-17524 (`68cb801`, merged 2026-08-06) added the loud `default:`
`logger.error`, which is the only reason this is visible at all. Before that it degraded silently.

This is the third instance of the same family and exactly what the 2026-08-06 dream distilled into
`patterns.md`: *emr-v2 trusts a precomputed label from gRPC, so an enumerated switch over that
label is guaranteed to run short.*

## Observed rate

- 32h window: 1 critical-typed test (1 sample), 1 `RANGE_ERROR` test (1 sample).
- Distinct `resultStatus` values in the same window for scale: `RESULT_NORMAL_M` 11,008,
  `RESULT_HIGH_ABNORMAL_M` 834, `RESULT_HIGH_MODERATE_ABNORMAL_M` 414, `RESULT_LOW_ABNORMAL_M` 260,
  `RESULT_HIGH_CRITICAL_M` 2 (=1 test), `RANGE_ERROR` 2 (=1 test).
- So ≈1 masked critical per day **on the EMR HL7 delivery path alone**, and the defect has existed
  for the life of this file. Historical total is unquantified.

## NOT done (deliberately)

- **No Jira ticket filed.** Per `feedback_defect_found_must_be_ticketed`, a defect must never be
  filed as type Bug without Leo confirming the classification. Dream runs autonomously; Leo decides.
- **No code change.** Fix is small and obvious (add the two switch arms) but this is a result-content
  / patient-safety path and belongs in a reviewed work session with a test matrix, not in dream.
- **Historical sizing not run.** ClickHouse `192.168.62.85` ports 8123/9000 were closed at run time
  (VPN down overnight; per `project_hl7_triage_db_port_blocked`, connecting the VPN mid-session kills
  live sessions, so I did not connect).

### [2026-08-09] Dream re-probe — no new victims in a 22h window (NOT a fix)

Prod pod `lis-emr-v2-deployment-prod-5f47cb8554-5tz22` (22h old), same grep as the discovery run:
- `RESULT_HIGH_CRITICAL*` / `RESULT_LOW_CRITICAL*` / `RANGE_ERROR`: **0 occurrences**.
- `level:error` lines: **0**.
- Input side measured so the zero means something: 1,882 total log lines,
  `RESULT_NORMAL_M` 185, `RESULT_HIGH_ABNORMAL_M` 60, `RESULT_HIGH_MODERATE_ABNORMAL_M` 15.

So the result path *was* running, and no critical-typed test came through it in this window.
Volume is ~60x lower than the 32h discovery window (11,008 `RESULT_NORMAL_M`) — a Sunday.
**This is consistent with the ~1-per-day estimate, not evidence the defect is gone.** Nothing was
changed; the missing switch arms are still missing. Still unticketed, still awaiting Leo.

### [2026-08-12] Dream re-probe — the default arm fires ~15x/day; the 08-09 zero was the anomaly

Datadog, `service:lis-emr-v2-deployment-prod "Unknown reference range type"`:

- **111 occurrences of the unmapped-type error, 2026-08-06 01:08Z → 2026-08-13 00:59Z**, continuous,
  still firing at probe time. This is the whole `default:` arm — the pattern search wildcards the
  type name, so the 111 covers every unmapped label, including the two `RESULT_HIGH_CRITICAL_M`
  occurrences already documented above. It is **not** a RANGE_ERROR-only count.
- **Last 2 days: 6 occurrences, and all 6 are `RANGE_ERROR`** (2026-08-11 19:00Z, 08-12 19:40Z,
  08-13 00:29/00:55/00:55/00:59Z) — raw lines read individually, all
  `Unknown reference range type: "RANGE_ERROR" (normalized: "RANGE_ERROR")`. No critical-typed
  label appears in this 2-day slice.

This changes two things in the record above:

1. The 2026-08-09 "0 occurrences in 22h" re-probe was a **quiet window, not a low base rate** —
   exactly the trap in [[feedback_never_conclude_breakage_from_a_quiet_window]], read in the other
   direction. The `default:` arm is hit ~**15x/day** averaged over the week, not ~1/day.
2. But the frequency and the **harm** are carried by different labels. `RANGE_ERROR` dominates the
   recent volume and step 3 below already parks it as possibly-legitimate TNP; the critical-high/low
   labels are rare and are the ones that put a real patient value behind a "not processed" flag.
   Anyone triaging on error count alone will mis-prioritise this: silencing `RANGE_ERROR` would
   remove most of the log noise and none of the patient-facing defect.
   **The per-label split, not the total, is the number to act on** — so the historical sizing in
   step 2 must break down by label rather than counting `default:` hits.

Still unticketed, still awaiting Leo. Nothing changed; the missing switch arms are still missing.

## Immediate next steps for a work session

1. Confirm with Leo/PM that `RESULT_HIGH_CRITICAL` → `HH` and `RESULT_LOW_CRITICAL` → `LL` is the
   intended mapping (the description/flag tables already imply it).
2. Size the historical blast radius over VPN: count delivered tests whose reference range type
   matched `%_CRITICAL%` since the emr-v2 result path went live, joined to transmitted results.
   That number decides whether affected customers need re-push/notification.
3. Decide `RANGE_ERROR` semantics separately — it may legitimately be TNP.
4. Replace the enumerated switch with a total mapping + a startup assertion over the known
   reference-range-type vocabulary, so the next unmapped label fails at deploy rather than
   silently on a patient result.

### [2026-08-14] Dream re-probe — rate dropped ~4x, and the split is now 100% RANGE_ERROR

Datadog `"Unknown reference range type"` over the last **48h** (2026-08-12 18:30Z → 2026-08-14 18:30Z):
**7 occurrences**, service `lis-emr-v2-deployment-prod`, all on `aks-userpool-...vmss000001`,
newest 2026-08-14T01:05:07Z. **Every one of them is `RANGE_ERROR`** — zero
`RESULT_HIGH_CRITICAL*` / `RESULT_LOW_CRITICAL*` in the window.

Two things follow, and they pull in opposite directions:
- **The noise is smaller than the 08-12 reading suggested.** ~3.5/day here vs the ~15/day implied
  by 111-over-7-days. The rate is not stable enough to extrapolate from any single window — this
  is the third window in a row (0/22h on 08-09, 111/7d on 08-12, 7/48h tonight) to give a
  materially different rate. Per [[feedback_never_conclude_breakage_from_a_quiet_window]], stop
  quoting a rate for this signal; quote the window and the label split.
- **The patient-facing defect is unchanged.** The critical-high/low arms are still missing from
  `mapReferenceTypeToStatus`; they are simply rare. A 48h window with zero critical labels is
  entirely consistent with the two documented occurrences being weeks apart. **Do not read the
  drop as the bug going away** — it is the same "per-label split, not the total" trap already
  written up in the section above, seen from the other side.

Still unticketed, still awaiting Leo. No code has changed.
