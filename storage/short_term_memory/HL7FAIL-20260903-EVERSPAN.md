---
id: HL7FAIL-20260903-EVERSPAN
title: LBS-1772 / Everspan (MDHQ) customer_not_found=MARY JO ALLEN — transfer order
  to Dr. Michael Ahmann by editing pod-local HL7 (no new integration)
category: emr_integration
status: completed
created: 2026-09-03
updated: 2026-09-03
related:
- LBS-1772
- HL7FAIL-20260730-TURNPAUGH
- HL7FAIL-20260722-MDHQ
- VP-17120
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
- INCIDENT-20260817-onprem-stale-deploy
- INCIDENT-2604156666
- LBS-1541
- LBS-1656
- LBS-1762
- LBS-1773
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
- VP-18034
- VP-18055
- emr-integration
- fhir-api
score: 1.1475
---

# HL7FAIL-20260903 — Everspan customer_not_found (Mary Jo Allen)

## What happened
- hl7_file_input 7012 (order_1089_1788372856_42.hl7, /everspanemr/orders/, MDHQ, onprem folder mapping id 165), received 2026-09-02 18:16Z, customer_not_found=MARY JO ALLEN, retry loop burning (4 -> 2 by fix time).
- Leo had already edited the HL7 "NPI" and asked why it still failed. Two separate reasons:
  1. Retry re-reads the OWNING POD's local copy (`/mnt/storage/EMR_storage/HL7Message_prod/MDHQ/Prod/Order/` on appserver04), never SFTP. Fetch dedups on `stfp_file_full_name` (`alreadyIngested`) and deletes remote after download, so an edit anywhere except the pod-local file is invisible.
  2. The local file HAD been edited (mtime 12:22 PDT) but only OBR.16 was changed (-> 1649323791). Customer resolution reads **ORC.12 first**, OBR.16 only as fallback (`hl7-order.processor.ts:152`, `parser.service.ts:170`). ORC.12 still carried Mary Jo Allen's NPI 1679369169.

## Diagnosis
- Mary Jo Allen = customer 51108, NPI 1679369169, clinic 66839 (EverSpan Life), signup 2026-05-22. Zero `ehr_integrations` / `order_clients` rows -> textbook add-provider case. Leo chose NOT to add an integration this time; file edit instead.
- Everspan LIVE FULL rows: 51902 Brad Jacobs 1184680258, 50793 Gianna Tomassetti 1326695347, 22376 (NPI 1649323791).
- **Trap**: NPI 1649323791 (Julie Kaesberg, the NPI Leo put in OBR.16) has TWO LIVE FULL ordering rows: 22376 (/everspanemr/, updated 04-30) and **50342 (/Prod/Orders/, clinic 153585, updated 06-26 — newer, wins resolveOrderingIntegration)**. Using it would have routed the order to clinic 153585, not Everspan. Also lis_core_v7 customer 22376 is Michael Ahmann (NPI 1720245806), not Kaesberg — ehr_integrations row 22376 carries a stale NPI.
- First attempt (mine, WRONG target): rewrote both fields to Gianna Tomassetti 1326695347 (single LIVE row, last 4 successes used it). Leo rejected it and pointed at **LBS-1772**: customer confirmed the order must go to **Dr. Michael Ahmann (customer 22376, practice 66839)**, no duplicate manual order, original intake preserved in `quarantined_orders` id 2. Reverted to the backup at 20:13:33Z, 4 min before the 20:17Z tick, so no Gianna order was created.
- Resolution path that makes Ahmann work (verified in `customer-detail-fetcher.service.ts`):
  - ORC.12.1 length <= 7 -> `fetchById(customerId)` -> `resolveOrderingIntegration([customerId])` (needs a LIVE ordering row for that customer_id; NPI irrelevant). "22376" would work.
  - ORC.12.1 longer -> `fetchByNpi` -> gRPC `getCustomerByNPINumber` (core `customer.customer_npi_number`) -> customerIds -> `resolveOrderingIntegration(customerIds)`. NPI **1720245806** (Ahmann's real NPI) -> core customers [4608, 22376]; only 22376 has a LIVE ordering row -> resolves to 22376 / clinic 66839. Chosen: `1720245806^AHMANN^MICHAEL^^^^^N` in ORC.12 AND OBR.16 (vendor-shaped, deterministic).
  - Leo's OBR.16 value 1649323791 would NOT have worked even in ORC.12: core maps that NPI to [23083, 38901, 50342, 51883] (never 22376), and 50342 has the newest LIVE row -> clinic 153585. ehr_integrations row cmjklwx10007r0xfes0lllobs (customer 22376) carries a stale customer_npi 1649323791 (core says 22376 = Ahmann 1720245806) — data smell, untouched.

## Fix (executed 2026-09-03 20:09Z-20:18Z, Leo direct request, LBS-1772)
- ssh leo@192.168.60.5 (password auth via expect; ~/ is NOT writable for leo, /tmp is). Backups in `/tmp/hl7_backup_leo/`: `order_1089_1788372856_42.hl7.orig-202609031309` (Leo's 12:22 version: ORC.12=1679369169, OBR.16=1649323791), `gianna-version.hl7` (my discarded attempt), `ahmann-version.hl7` (final, md5 7e4b2924dd8244479cc36a2a29324013, 495 bytes).
- Final file: ORC.12 and OBR.16 both `1720245806^AHMANN^MICHAEL^^^^^N`; everything else byte-identical to the vendor original. Verified md5 from host AND from inside pod `lis-emr-v2-deployment-prod-7775dcd74b-7mfnb` (`/EMR_storage/...`). LF segment separators (parser already accepted LF at 19:32Z).
- retry_num NOT touched: 4 -> 3 (19:47Z) -> 2 (20:02Z, pre-edit) -> 1 (20:17Z, read the reverted Mary Jo file while CIFS was stuck). One attempt left for the 20:32Z tick; if it burns to 0, bump `retry_num=3` (VP-17120 path).

## CIFS incident during the edit (20:14Z-20:18Z) — worth remembering
- `/mnt/storage` is a CIFS (SMB 2.1, cache=strict) mount of `//10.0.0.101/storage`; the pod mounts the same share, so both views are the SMB server's truth.
- 1st `sed -i` (Gianna) worked with a "preserving permissions: Operation not permitted" warning (target is root-owned). 2nd `sed -i` failed silently; my `rm -f` then put the file into **delete-pending (Links: 0)**: reads via existing handles still worked (pod's 20:17Z tick still parsed the OLD content), but every new open/cp/mv failed with "No such file" / "File exists" / "Permission denied". `drop_caches` did not help.
- Cause: Leo had `less order_1089_1788372856_42.hl7` open on the host (PID 331205, since 13:12 PDT) — SMB keeps a delete-pending file alive while any handle is open. `/proc/fs/cifs/open_files` + `lsof | grep <file>` found it. Killing the pager completed the delete; `cp` then created the file cleanly.
- Rule: on this share, edit by `cat new > file` (in-place write, no rename) and check `lsof` for pagers/editors holding the file BEFORE any rm/rename.

## BullMQ jobId collision — why "bump retry_num back to 5" silently does nothing
- Rescan enqueues `{ jobId: \`hl7-${id}-r${retry_num}\` }` (`hl7-order-fetch.service.ts:298`); queue keeps completed jobs 24h (`removeOnComplete: { age: 86_400 }`, module line 98). BullMQ ignores `add()` for an existing jobId in ANY retained state.
- Timeline for 7012: initial job `hl7-7012` (18:16Z). Leo bumped retry to 5 before 19:32Z -> r5 (19:32Z), r4 (19:47Z), r3 (20:02Z), r2 (20:17Z) all completed with `{status: customer-not-found}` and are still in redis. Leo bumped to 5 again at 20:26:31Z -> 20:32Z tick logged "1 retry(s) re-enqueued" but NO "Processing HL7 file id=7012" — the r5 add was de-duped. Every further tick would repeat that forever while retry_num stays in {2,3,4,5}.
- Diagnosis path: pod redis sidecar (`kubectl exec -c redis -- redis-cli`): `--scan --pattern 'bull:process-hl7-file:hl7-7012*'`, `ZSCORE bull:process-hl7-file:completed <jobId>`, `HMGET <job> returnvalue finishedOn`.
- Fix applied 20:41:09Z (emr-v2 app account): `UPDATE hl7_file_input SET retry_num=8 WHERE id=7012 AND parse_finished=0 AND retry_num=5 AND file_name=...` (1 row) -> r8/r7/r6 are fresh ids = 3 real attempts before hitting the used range again.
- Rule: when re-placing a row, set retry_num to a value whose `-r{n}` has never been enqueued for that id in the last 24h (check redis, or just go ABOVE the highest used). Bumping to the same number as before is a no-op. This deserves a code fix (include a nonce / last_parse_time in the jobId, or delete the completed job on re-place) — candidate ticket.

## Gotchas worth keeping
- "I changed the NPI in the HL7 file" must be followed by: WHICH copy (pod-local vs SFTP vs laptop) and WHICH field (ORC.12, not OBR.16).
- Before substituting a provider NPI, check it has exactly ONE LIVE ordering row; multi-row NPIs resolve by updated_at DESC and can silently land in another clinic.
- The 15-min tick that fires between diagnosis and edit burns one retry_num on the old content (here 20:02Z, 3 -> 2). Check retry_num > 0 remains after the edit; bump to 3 only if it hit 0.

## Reprocess + outcome
- 20:47:34Z tick enqueued r8 -> parsed OK: parse_finished=1, sample_id 2629319, file archived to `.../Order/archive/order_1089_1788372856_42.hl7`. Pod log: "No ehr_integrations match for NPI=1720245806 MSH.4=22376 — falling through to parser" (pre-step only affects contact email) then parser `fetchByNpi` resolved 22376.
- Core-verified (lis_core_v7): sample 2629319 / accession 2609036689 -> order 11476195, customer 22376 (sample AND order), clinic 66839, isActive=1, order_status order_received, patient THERESA BERNER (patient_id 3279045), sample_order_method EMR. Exactly ONE sample for that patient — no duplicate.
- `hl7_file_input.last_error` still says customer_not_found=MARY JO ALLEN (stale text, known from TURNPAUGH); customer_not_found column cleared; order_input now populated.
- `quarantined_orders` id 2 still status=OPEN (expires 2026-09-09). Left for Leo: no reprocess/resolve API was used, so the quarantine row does not know the order landed. Flagged in report.

### [2026-09-03] Dream closeout audit — outcome verified on prod (read-only)
- hl7_file_input 7012: `parse_finished=1`, `last_parse_time=2026-09-03 20:47:34Z`, `retry_num=8`, `sample_id=2629319`,
  `julien_barcode=2609036689`, payment_id af3620ee-…; emr_sample 2629319 → emr_order_id 0000008832. The retry_num=8 re-place
  worked on its first fresh jobId (r8). `last_error` still reads `customer_not_found=MARY JO ALLEN` — the column is not cleared on
  success; success = parse_finished + sample_id.
- LBS-1772 Jira Done 2026-09-03 15:11 PDT (Leo). No other unfinished MDHQ rows except 7006 (MARK MASCARI, unrelated, retry_num 0).
- Status normalized `done` → `completed` for the scoring engine.
