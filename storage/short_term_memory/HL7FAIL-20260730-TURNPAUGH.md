---
id: HL7FAIL-20260730-TURNPAUGH
type: stm
category: emr_integration
status: completed
created: 2026-07-31
updated: '2026-07-31'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7-NPI-PRACTICE-MATCH-20260820
- HL7FAIL-20260722-MDHQ
- HL7FAIL-20260729-PLESSEN
- INCIDENT-20260808-critical-result-tnp
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
- customer-not-found
- mdhq
- add-provider
- retry-rescan
- turnpaugh
summary: 'hl7_file_input 6746 (order_28984_1785429636_83.hl7, /turnpaughemr/orders/,
  MDHQ) failed customer_not_found=VINCENT GROVE: provider had VA account (customer
  51012, NPI 1043041429, clinic 13505 Turnpaugh) but zero ehr_integrations rows —
  the clinic-level FULL_INTEGRATION row (customer_id=-1) is a result-only migration
  row with ordering_enabled=0 and no NPI, so it never participates in order routing.
  Fixed per add-provider playbook: INSERT ehr_integrations (mirror practice LIVE FULL
  peer 9075, msh06=13505 per 2026-04+ convention) + order_clients id 2333; retry_num
  still had budget so no bump needed; on-prem pod retry-rescan re-parses from retained
  local file. Re-parsed OK at 21:16Z: sample 2607187 / order 11455096, customer 51012,
  clinic 13505, active, no duplicates (core-verified). Leo direct request, no Jira
  ticket; requested_by=customer_not_found-fix-20260731.'
jira_status: none
score: 0.4752
---

# HL7FAIL-20260730 — Turnpaugh customer_not_found (Vincent Grove)

## What happened
- hl7_file_input 6746 (order_28984_1785429636_83.hl7, /turnpaughemr/orders/, MDHQ), received 2026-07-30 16:45Z, customer_not_found=VINCENT GROVE, retry loop burning down (4→3 by fix time).
- Leo's initial confusion (worth keeping): "the whole clinic has FULL_INTEGRATION, why fail?" — the clinic-level row (id cmjxar7cb00lf0xfq4g3nook7, customer_id="-1", requested_by=migration_script_emr_result) is a RESULT-ONLY migration artifact: ordering_enabled=0, customer_npi=NULL. Order routing is per-provider NPI (ORC.12 → resolveOrderingIntegration), so a clinic-level row with no NPI and no ordering flag is invisible to intake. Every provider at the practice has their OWN FULL_INTEGRATION LIVE row (customers 9075–9088, msh06=9075 legacy-style).

## Diagnosis
- Vincent Grove: customer 51012, NPI 1043041429, login vince@turnpaughhwc.com (customer_details @60.3:3307).
- Clinic confirmed via lis_core_v7._clinictocustomer: 13505 (matches failing row's folder). lis_core_v7 is on Azure (lisportalprod2), NOT on 60.3.
- ehr_integrations + order_clients: zero rows for customer/NPI → textbook add-provider case (same shape as HL7FAIL-20260722-MDHQ).

## Fix (executed 2026-07-31, Leo direct request — no Jira ticket)
- INSERT ehr_integrations id cms9fj5r59ptpnhmbfbk0f42j: mirror peer cmjxaq4vg00bj0xfqzjqy9lkp (Chris Turnpaugh 9075, LIVE FULL) column-for-column; overrides: customer_id=51012, NPIs=1043041429, msh06_receiving_facility=13505 (2026-04+ convention; peers keep legacy 9075-style msh06 — untouched), integration_origin=NEW_INTEGRATION, contact=Leo, requested_by=customer_not_found-fix-20260731. report_option CLASSIC follows practice.
- INSERT order_clients id 2333 (Vincent Grove / 51012 / NPI / 13505 / MDHQ / /turnpaughemr/orders/).
- Discipline: single transaction, 3 pre-check guards (no existing rows, peer state), dry-run ROLLBACK first, commit, 100% post-commit verify on independent read connection. Script: scratchpad fix_vincent_grove.sh pattern.
- sftp_folder_mapping id 113 (/turnpaughemr/orders/, pipeline_location=onprem) already existed — untouched; on-prem pod owns the retry.

## Gotchas worth keeping
- emr-v2 .env DATABASE_URL password is URL-ENCODED (contains %xx) — mysql CLI auth fails with the raw substring; urllib.parse.unquote it first. (lis_core_emr read acct worked fine; only the app acct URL needed decoding.)
- retry_num was still >0 at fix time → NO manual bump needed; the pending retry budget + VP-17120 rescan picks the row up on the next 15-min tick automatically. Only bump 0→3 when exhausted.
- A retry tick that fires between diagnosis and commit burns one retry_num on the old (broken) state — expect one more failed tick in the timeline before recovery.

## Reprocess + outcome
- 21:01Z tick fired pre-commit (burned retry 4→3, failed again as expected); 21:16:08Z tick re-parsed successfully: parse_finished=1, sample 2607187.
- Core-verified (lis_core_v7): sample 2607187 → order 11455096, customer 51012, clinic 13505, isActive=1, patient MATTHEW WATSON; zero duplicate samples for patient 3263034 + customer 51012. (order_info has no sample_id column — join via sample.order_id.)
- hl7_file_input.last_error keeps the stale "customer_not_found=VINCENT GROVE" text after success — parse_finished=1 + sample_id is the success signal, not last_error.

## Open items
- Clinic 13505 has DUPLICATE LIVE FULL rows per provider (9075/9077/9079–9088 each appear twice: cmj99… and cmjxaq… id families, same customer so currently harmless for routing). Flagged to Leo 2026-07-31; cleanup is his call.
