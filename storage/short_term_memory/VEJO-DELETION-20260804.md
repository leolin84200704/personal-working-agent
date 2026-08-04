---
id: VEJO-DELETION-20260804
type: stm
title: Deleted VEJO / VEJO Ecomm / VEJO Program integrations from prod (Leo direct request)
status: completed
category: emr_integration
created: 2026-08-04
updated: 2026-08-04
relations:
  sibling: []
  unblocked_by: []
links: []
tags: [vejo]
summary: "Deleted all 3 VEJO integrations (vendors 17/18/43) from prod lis_emr: 41 rows across 7 tables, transaction with count guards, full backup at ~/src/credential/vejo-deletion-backup-20260804.json. Zero activity ever (0 hl7, 0 results, 0 samples). Reverse-audit clean."
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
