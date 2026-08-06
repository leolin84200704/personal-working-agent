---
id: HL7FAIL-20260722-MDHQ
type: stm
category: emr_integration
status: completed
created: 2026-07-23
updated: '2026-07-23'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7FAIL-20260729-PLESSEN
- HL7FAIL-20260730-TURNPAUGH
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
- VP-17517
- VP-17537
- VP-17538
- VP-17539
- VP-17544
- VP-17589
- VP-17591
- emr-integration
- fhir-api
tags:
- customer-not-found
- mdhq
- add-provider
- retry-rescan
summary: 'Two 07-22 hl7_file_input failures (6673 Caroline Xanthakis / 6677 Angela
  Jordan, both MDHQ) were customer_not_found: providers had VA accounts+NPIs but zero
  ehr_integrations rows. Fixed per VP-16765 playbook: INSERT ehr_integrations x2 (mirror
  practice LIVE peer, msh06=clinic_id per 2026-04+ convention) + order_clients x2,
  then bump retry_num 0->3; on-prem pod retry-rescan (VP-17120) re-parsed from its
  retained local file on the next 15-min tick. Samples 2602089/2602090 created, correct
  customer+clinic, no duplicates. No Jira ticket (Leo direct request); requested_by=customer_not_found-fix-20260723.'
jira_status: none
score: 0.547
---

# HL7FAIL-20260722 — MDHQ customer_not_found x2 (Caroline Xanthakis / Angela Jordan)

## What happened
- hl7_file_input 6673 (order_337_1784682209_58.hl7, /evolvefuncregmedemr/orders/) and 6677 (order_5534_1784734174_55.hl7, /reveal-vitality/orders/), both 2026-07-22, emr_service=MDHQ, customer_not_found, retry_num exhausted to 0.
- Root cause: providers had VA customer accounts + NPIs but NO ehr_integrations row → resolveOrderingIntegration (LIVE + ordering_enabled gate) found nothing.

## Fix (executed 2026-07-23, Leo direct request — no Jira ticket)
- Caroline Xanthakis: customer 51588, clinic 138167 (Evolve Functional & Regenerative Medicine), NPI 1205768173 → ehr_integrations id c2an835imi910gcxw7iloqqh1ty8dn, order_clients id 2330.
- Angela Jordan: customer 41120, clinic 125316 (Reveal Vitality), NPI 1720978190 → ehr_integrations id c2o0pt77vjf1hunucr2gm2dehmaolk9, order_clients id 2331.
- Mirrored each practice's LIVE FULL peer (43606 / 6731) column-for-column; identity fields + msh06=clinic_id (2026-04+ convention; peers still carry legacy customer-id msh06 — NOT touched, alignment needs vendor coordination). report_option follows practice peer (Evolve=PERSONALIZED, Reveal=CLASSIC). sftp_folder_mapping already existed (practice-level) — untouched.
- Transaction with pre-check guards (no existing row for customer/NPI, peer in expected state), dry-run first, in-tx verify, then commit; 100% post-commit verify.

## Reprocess + outcome
- customer_not_found is retryable since VP-17120; bumped retry_num 0→3 AFTER integration commit. Folder pipeline_location=onprem → on-prem pod owns the retry and re-reads its retained local file (failure does not archive). Next 15-min cron tick re-parsed both.
- Result: 6673 → sample 2602089 / order 11450176 (cust 51588, clinic 138167, active, KAREN SHIDLER); 6677 → sample 2602090 / order 11450177 (cust 41120, clinic 125316, active, NOREEN FOISY). Core-DB verified (lis_core_v7), zero duplicate samples.

## Gotchas worth keeping
- last_update_pod_name "lis-emr-v2-deployment-prod-*" is AMBIGUOUS: the on-prem cluster has a deployment with the SAME name as the AKS one. Check sftp_folder_mapping.pipeline_location to know which pod owns a folder's rows/files — don't assume AKS.
- The original HL7 content lives ONLY in the owning pod's local file (order_input often null in hl7_file_input) — reprocessing via retry_num is the only way to "re-place" such an order; hand-crafting is impossible without the file.
- ehr_vendors is the SFTP credential source (post VP-17460); MDHQ = vendor id 1, host 34.199.194.51:2210.

## Open items
- Peers' msh06 (6731/43606 = customer-id style) unaligned with practice-id policy — needs MDHQ coordination if Leo wants practice-wide alignment.
- No Jira ticket exists; create one retroactively if PM tracking needs it.
