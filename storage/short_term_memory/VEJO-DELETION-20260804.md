---
id: VEJO-DELETION-20260804
type: stm
title: Deleted VEJO / VEJO Ecomm / VEJO Program integrations from prod (Leo direct
  request)
status: completed
category: emr_integration
created: 2026-08-04
updated: 2026-08-04
relations:
  sibling: []
  unblocked_by: []
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
- BIOINSIGHTS-onboarding
- FHIR-ONDEMAND-RESULT
- HL7FAIL-20260722-MDHQ
- HL7FAIL-20260729-PLESSEN
- HL7FAIL-20260730-TURNPAUGH
- INCIDENT-20260808-critical-result-tnp
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
- emr-integration
- fhir-api
tags:
- vejo
summary: 'Deleted all 3 VEJO integrations (vendors 17/18/43) from prod lis_emr: 41
  rows across 7 tables, transaction with count guards, full backup at ~/src/credential/vejo-deletion-backup-20260804.json.
  Zero activity ever (0 hl7, 0 results, 0 samples). Reverse-audit clean.'
score: 0.7127
---

# VEJO integration deletion — 2026-08-04

## Origin
Leo direct request (no Jira ticket): "delete the integration with the below: VEJO / VEJO Ecomm /
VEJO Program". Same day as the on-prem decommission work (unrelated task, done while waiting for
the VP-17595 staging deploy).

## Pre-deletion inventory (all via prod pod exec, read-only first)
- ehr_vendors 17 (VEJO) / 18 (VEJOEcomm) / 43 (VEJOProgram), all pointing at SFTP 45.24.217.155
  with per-vendor accounts. 43 was a migration_script row from emr_sftp_source id 16.
- **Zero activity EVER**: hl7_file_input 0 rows all-time, result_transmission_records 0,
  emr_sample 0 — created 2025-12-24 (17/18) and migrated 2026-01-02 (43), never used.
- FK sweep across all 33 lis_emr tables (ehr_vendor_id / integration_id columns) found the full
  reference set before deleting — first pass missed practice_integrations /
  provider_integration_memberships / sftp_folder_mapping / ehr_vendor_sftp_templates.

## Deleted (41 rows, single transaction, per-table count guards, commit only on exact match)
| table | n | ids |
|---|---|---|
| provider_integration_memberships | 9 | 243,244,245,364,365,367,368,430,585 |
| practice_integrations | 7 | 165,322,323,324,329,336,426 |
| ehr_integrations | 9 | cmjklwnp1/wns6/wnvb, cmjklx4we/4zc/52v/5kr/6di, cmjxaql1u (cuids) |
| order_clients | 7 | 1459,1460,1461,1485,1498,1538,1649 |
| ehr_vendor_sftp_templates | 3 | 17,18,26 |
| sftp_folder_mapping | 3 | 68,69,266 |
| ehr_vendors | 3 | 17,18,43 |

## Backup / restore
Full row dump (JSON, includes SFTP credentials — kept OUT of git):
`~/src/credential/vejo-deletion-backup-20260804.json` (30443 bytes). Restore = re-INSERT from it.

## Reverse-audit (broader LIKE %vejo% across name/path columns)
All 7 tables + ehr_vendor_applications: 0 rows. Only remnant: 3 rows in
`emr_sftp_source_retired_20260720` — inert archive table (VP-17460 retirement), left untouched
as historical record.

## Effect
Order-fetch cron stops polling the 3 dead VEJO SFTP accounts on 45.24.217.155; the 9 LIVE-but-
never-used integrations no longer appear in any routing.
