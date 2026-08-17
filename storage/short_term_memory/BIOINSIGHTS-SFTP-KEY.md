---
id: BIOINSIGHTS-SFTP-KEY
summary: BioInsights SFTP account is key-only (no password) — added sftp_private_key
  columns to all 3 credential stores + plumbed privateKey through result-push and
  order-fetch pipelines. PR
status: active
category: emr_integration
created: 2026-07-20
updated: '2026-07-23'
links:
- BETA-E2E-20260729
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
- VP-17691
- VP-17715
- emr-integration
- fhir-api
score: 0.4196
---

# BIOINSIGHTS-SFTP-KEY — key-based SFTP auth support

## Context

- BioInsights provisioned `vibrant-wellness @ sftp.bioinsights.com:2022`, **key-based auth only** (no password on either end). Customer verified the account works via WinSCP with their key.
- All 3 credential stores (`ehr_vendors.sftp_password`, `ehr_integrations.sftp_password`, `emr_sftp_source.password`) were password-only → neither pipeline could auth.
- `SftpConnectionService` already supported `privateKey` (PEM, preferred over password) — only the admin manual-connect API used it; DB-driven paths did not.
- No Jira ticket exists for BioInsights (JQL `text ~ "BioInsights"` = 0 hits, 2026-07-20).

## Work log

### [2026-07-20]

Leo approved: key stored plaintext in DB (same posture as existing passwords; encryption = follow-up covering both), both pipelines, 3 commits for stepwise rollback.

- Branch `feature/leo/bioinsights-sftp-key` off origin/staging, PR **#275 draft → staging**: https://github.com/Vibrant-America/lis-backend-emr-v2/pull/275
- Commit 1 `b6dc99d` schema only: nullable `sftp_private_key TEXT` (ehr_vendors, ehr_integrations), `private_key TEXT` (emr_sftp_source) + `prisma/migrations/20260720_add_sftp_private_key/migration.sql` + schema.test.prisma sync
- Commit 2 `517e396` result push: `getSftpConfig()` resolves key (vendor or integration level), `uploadHL7File` → `connect({privateKey})`
- Commit 3 `365e30b` order fetch: `loadCredentialStores()` accepts password-OR-key rows (was password-only → key-only folders silently skipped at `hl7-order-fetch.service.ts` guard), key carried through `HostGroup`; VP-17385 drift diff now includes `privateKey` (field names only, never values)
- Tests: sftp.service.spec 7 passed (4 new), hl7-order-fetch.service.spec 30 passed (5 new), full suite 83/83 suites / 890 passed, nest build clean
- Worktree removed after push (feedback_delete_worktree_after_ticket)

## Deploy order (critical)

Prod is NOT Prisma-managed. Apply migration SQL to staging (192.168.60.11) + prod (lisportalprod2) **BEFORE** deploying code — commits 2/3 `select` the new columns; deploy-first = 500 on those queries (VP-16832 class).

### [2026-07-20 15:40] Migration APPLIED to both DBs (Leo directed)

- Runner: `scripts/_bioinsights-sftp-key-migrate.ts` (mysql2, idempotent pre-check + row-count guard + 100% column verify + dormant check); probe: `scripts/_bioinsights-live-probe.ts` (both gitignored `_*.ts`)
- **Staging** 192.168.60.11: 3 columns added, TEXT/nullable OK, rows 11/46/3 unchanged, all NULL
- **Prod** lisportalprod2: 3 columns added, TEXT/nullable OK, rows 33/1268/30 unchanged, all NULL
- Unit suite re-run on PR branch in fresh worktree: 83/83 suites, 890 passed
- **Live verify (prod, post-ALTER)**: old-code column-set reads on all 3 tables OK; order-fetch cron 15:45 tick ingested a new hl7_file_input row (received_time 15:45:23 > migration ~15:41) = order pipeline healthy on migrated DB. Result push: no organic traffic since (event-driven, Sunday), but its reads verified via the column-set probe.
- DB now AHEAD of deployed code (safe direction). PR #275 can merge anytime.
- Gotcha: `hl7_file_input` has NO created_at — use `received_time` / `updated_time`

## Open items

- [x] PR #275 MERGED to staging + promoted to main (PR #276) 2026-07-20; prod runs 2a33fe1 (dream resolve 2026-07-22, source: VP-17460 env facts + BIOINSIGHTS-onboarding)
- [x] Vendor row setup DONE 2026-07-23: perms fixed by vendor (Serdar), ehr_vendors id=46 (key-based, is_public=0) + sftp_folder_mapping id=281 (pipeline_location=cloud) inserted + live-verified — details in BIOINSIGHTS-onboarding (dream resolve 2026-07-23)
- [ ] Possibly file a Jira ticket for the BioInsights integration and link PR
- [ ] Encryption follow-up: encrypt sftp_password + sftp_private_key at rest (schema comment has flagged this since before)
