---
id: BIOINSIGHTS-onboarding
type: stm
category: emr_integration
status: active
relations:
  unblocked_by: []
  sibling:
  - BIOINSIGHTS-SFTP-KEY
unblock_when: 'BioInsights grants account perms (test: sftp key-auth to sftp.bioinsights.com:2022
  then ls / — currently auth OK but ls/stat/put all fail); waiting on Thomas reply
  to 2026-07-21 email'
created: 2026-07-21
updated: '2026-07-27'
links:
- BETA-E2E-20260729
- BIOINSIGHTS-SFTP-KEY
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
- VP-16968
- VP-16987
- VP-17076
- VP-17117
- VP-17120
- VP-17136
- VP-17283
- VP-17286
- VP-17344
- VP-17385
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
- repos
tags:
- bioinsights
- sftp
- key-auth
- vendor-onboarding
summary: 'New EMR vendor BioInsights — first key-based (non-password) SFTP integration.
  Code shipped: emr-v2 PR no VP ticket yet): migration 20260720_add_sftp_private_key
  adds nullable sftp_private_key to ehr_vendors + ehr_integrations and private_key
  to emr_sftp_source; order fetch accepts key-only credential rows (VP-17385 drift
  check extended to privateKey); result push passes key through to connect. Migration
  must be applied MANUALLY to prod (lisportalprod2) and staging (192.168.60.11) BEFORE
  deploying the code (prod not Prisma-managed). Connection per vendor (Thomas): sftp.bioinsights.com:2022,
  user vibrant-wellness, ed25519 keypair (PPK v3 unencrypted at ~/Downloads/bioinsights_key.ppk;
  emr-v2 needs OpenSSH PEM — convert with puttygen). 2026-07-21 verified from local:
  auth OK, but account has ZERO perms (ls/stat/put all fail) — vendor-side provisioning
  incomplete. Migration verified applied prod+staging; PR 33 existing password vendors
  unaffected; AKS pod egress to bioinsights:2022 OK. 2026-07-21 email sent to Thomas
  (perms + dir layout + sample HL7). STATUS: waiting on vendor reply.'
jira_status: none
score: 0.5125
---

# BioInsights EMR vendor onboarding (SFTP, key-based auth)

## Facts

### [2026-07-21 12:00]
- Vendor connection (from Thomas @ BioInsights, tested OK by company IT):
  - Host `sftp.bioinsights.com`, port `2022`, username `vibrant-wellness`
  - Auth = ed25519 keypair, comment `vibrant-wellness-bioinsights-sftp`
  - Private key: `~/Downloads/bioinsights_key.ppk` (PPK v3, UNENCRYPTED — should move out of Downloads into credential store)
  - Public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF1/iaD2dcHdpj/WgGDC6MvRmMdqGa0oMjfixyQ/O45t`
- emr-v2 SFTP client wants `privateKey` as **OpenSSH PEM string** (`sftp-connection.service.ts`), NOT ppk. Convert: `puttygen x.ppk -O private-openssh -o x.pem` (brew install putty).
- Local connection test 2026-07-21: auth SUCCEEDS; `ls /` returns "Couldn't read directory: Failure" (chroot/perm); probed orders/results/inbound/outbound/in/out/upload/download/files/vibrant*/home — none exist. **Remote dir layout unknown.**

## Code state (done)
- `lis-backend-emr-v2` PR #275 MERGED to main 2026-07-20 (also in staging). Branch `feature/leo/bioinsights-sftp-key`. Commits:
  - `b6dc99d` migration `20260720_add_sftp_private_key`: ALTER ehr_vendors ADD sftp_private_key TEXT NULL; ehr_integrations ADD sftp_private_key; emr_sftp_source ADD private_key
  - `365e30b` order fetch: loadCredentialStores accepts password-OR-key rows; key carried through HostGroup into connect(); drift compare includes privateKey (names only, never values)
  - `517e396` result push: key pass-through in sftp.service
- No VP ticket exists for this onboarding (Jira text search 0 hits as of 2026-07-21).

### [2026-07-21 22:30] Verification pass (migration/deploy/regression)
- **Vendor account has ZERO permissions**: auth OK but ls/stat/cd/put ALL fail at root and every probed path (20+ naming conventions + write probe). Server-side provisioning incomplete — BLOCKED ON VENDOR (Thomas). IT's "tested OK" was auth-handshake only.
- **Migration applied on BOTH DBs**: prod (via AKS pod prisma, lis_emr) and staging (staging pod, root@lis_emr) both have ehr_vendors.sftp_private_key + ehr_integrations.sftp_private_key.
- **emr_sftp_source table does NOT exist in either prod or staging DB** — migration's 3rd ALTER inapplicable. Harmless: VP-17460 (merged after PR #275) removed the emr_sftp_source fallback from the fetch path; main reads ehr_vendors only via loadVendorCredentials. NOTE pre-existing landmine: auto-integrate integration-request.service.ts still queries prisma.emrSftpSource (would 1146 at runtime) — unrelated to BioInsights, not touched.
- **Deploy confirmed**: prod image 60fc05cd (= origin/main HEAD, merge PR #280) and staging image 17c5b70 BOTH contain PR #275 (verified via git merge-base --is-ancestor).
- **No regression risk to existing integrations**: prod ehr_vendors 33 rows with sftp_host — all 33 password, 0 key, 0 neither → password-OR-key change alters no existing row's behavior. 12h prod logs: order-fetch 0 errors (ticks normal), sftp 0 errors.
- **Egress OK**: prod AKS pod TCP-connects to sftp.bioinsights.com:2022 directly — no allowlist negotiation needed (unlike VP-17312 batch-5 vendors).

### [2026-07-21 23:00] Email sent to Thomas — WAITING ON VENDOR
- Leo sent the drafted email to Thomas @ BioInsights asking for: (1) account read/write permission provisioning (auth works, zero perms), (2) directory layout (orders pickup dir / results drop dir / archive convention), (3) sample HL7 order files for parsing + transformer-mapping assessment.
- Our side fully ready: PR #275 deployed prod+staging, migration applied, egress from AKS pod to sftp.bioinsights.com:2022 verified.
- NEXT ACTION when Thomas replies: re-run connectivity test (ls + put probe), inspect dir layout, review sample HL7 → decide transformer mapping + integration scope (order/result/bidirectional, which practices) → then gated ehr_vendors INSERT.

### [2026-07-23 10:50] Vendor perms fixed — E2E connectivity PASS + vendor/mapping rows INSERTED (prod)
- Serdar SANRI (Head of Eng, serdar@bioinsights.com — new contact, was Thomas) fixed server perms, created `incoming/` + `outgoing/` at root.
- Local E2E test ALL PASS: ls root/incoming/outgoing OK; put+get roundtrip diff-verified in BOTH folders. Test files `vibrant_test.txt` left on server as evidence (harmless: fetch filter only picks `.hl7,.HL7`).
- Key recovered: ppk still at `~/Downloads/bioinsights_key.ppk` (macOS TCC blocks *listing* Downloads — direct full-path access works; earlier "file gone" was a sandbox illusion). Converted to OpenSSH PEM via puttygen; pubkey matches recorded fingerprint.
- **Prod INSERTs applied 2026-07-23 ~10:47 PT** (single transaction, pre-check guards, in-tx 100% verify; runner `scripts/_tmp-bio-apply.js` pattern):
  - `ehr_vendors` id=46: code=BIOINSIGHTS, sftp.bioinsights.com:2022, user vibrant-wellness, sftp_password=NULL, sftp_private_key=PEM(444 chars), ordering_path=/outgoing/, result_path=/incoming/, **is_public=0** (flip at go-live), created_by/updated_by=Leo
  - `sftp_folder_mapping` id=281: /outgoing/ -> /BIOINSIGHTS/Prod/Order/, emrName=BIOINSIGHTS, use_v2_pipeline=1, **pipeline_location=cloud** (FIRST cloud order folder ever — all other 197 rows are onprem; chosen because AKS egress verified, on-prem egress NOT verified; doubles as VP-17312 order-side canary)
- **ASSUMPTION pending vendor confirm**: direction convention = we PICK UP orders from `/outgoing/`, DROP results into `/incoming/` (from BioInsights server's perspective). Asked Serdar in reply draft. If reversed: 1-column UPDATEs (mapping.server_folder + vendor paths swap).
- Safety: even if files arrive now, no ehr_integrations rows exist -> parse fails at customer_not_found, no orders placed.

### [2026-07-23 11:10] Pipeline LIVE-verified + archive dir created + reply email SENT — WAITING ON VENDOR
- 11:00 PT cron tick (AKS cloud pod): "Scanning 1 v2-enabled SFTP folder(s) [cloud]" -> connected sftp.bioinsights.com:2022 with the DB-stored key (1/3 attempt, 1621ms) -> "fetch complete: 0 file(s) from 1/1 folder(s)". Order pipeline is live-scanning BioInsights every 15 min.
- Created `/outgoing/archive/` on vendor server + verified rename into it (= fetcher's exact post-fetch move). Default HL7_REMOTE_POST_FETCH_ACTION=archive flow works with zero config. Test file now at `/outgoing/archive/vibrant_test.txt` (+ one in `/incoming/`).
- Leo SENT the reply email to Serdar 2026-07-23: connectivity confirmed, archive explained, asked to confirm direction convention (orders=outgoing/, results=incoming/) and to have clinical team prep sample HL7.
- STATUS: waiting on Serdar — (a) direction confirm, (b) sample HL7 files. When samples land in /outgoing/ the pipeline auto-ingests; they will fail safely at customer_not_found (no ehr_integrations yet) and be visible in hl7_file_input for parse/mapping review.
- NEXT ACTION on vendor reply: review ingested sample rows in hl7_file_input + raw files in /BIOINSIGHTS/Prod/Order/; if direction reversed, UPDATE mapping.server_folder + swap vendor ordering/result paths + mkdir archive under the other folder; then define practice scope -> ehr_integrations INSERTs (gated) -> flip is_public=1 at go-live.

### [2026-07-27] Practice scope arrived + ehr_integrations INSERTED — first BioInsights practice live
- Email (Serdar thread): Office = JAG Holdings Group, LLC, Provider 30248, Practice 132493. Payton @ Canvas Medical CC'd to continue integration (BioInsights appears to ride on Canvas Medical's EMR platform).
- 30248 = JAGHP (VP-16987 quarterly CSV client). Identity verified via existing prod row: (30248,132493) already had POWER2PRACTICE RESULT_ONLY LIVE (vendor 4, NPI 1730269200, msh06=30248, /public/, onprem).
- **INSERTED `ehr_integrations` id=cms3icsz700010xlgywfuj8do** (prisma create in guarded tx, dry-run first, in-tx verify + reverse-audit clean): vendor 46 BIOINSIGHTS, FULL_INTEGRATION, LIVE, o1/r1/s1, use_vendor_sftp_config=1 (host+key from vendor row), msh06=**132493** (Practice ID convention), sftp_result_path=/incoming/, ordering via folder mapping /outgoing/ (id=281), report_option=CLASSIC (followed sibling), kit_delivery_option=NO_DELIVERY + kits_options=2 (no-oc fallback — vendor kit behavior UNCONFIRMED), pipeline_location=**cloud**, NPI borrowed from sibling, requested_by=BIOINSIGHTS-onboarding.
- **DOUBLE RESULT DELIVERY flag**: both rows LIVE+result_enabled=1 -> results for 30248 now push to BOTH P2P /public/ AND BioInsights /incoming/. Leo to decide: retire P2P row (REJECTED per removal playbook) or keep during transition.
- Cyberduck access for Leo: key converted to ~/.ssh/bioinsights_vibrant-wellness.pem (2026-07-27); ppk still unencrypted in ~/Downloads (secure-store follow-up stands).
- Still waiting on vendor: sample HL7 files + direction-convention confirm (orders=/outgoing/ assumption unchanged). ORC-12 must carry 30248 for orders to resolve.
- [2026-07-27] Leo SENT reply to Serdar+Payton: technically ready end-to-end; "internal coordination step" (= P2P transition confirm, old platform not named externally); will update immediately; invited sample HL7 into outgoing/. PENDING DECISIONS: (a) P2P row retirement — double delivery to /public/ + /incoming/ is ACTIVE until decided (30248's next report_finished pushes both); manual repush w/o integration_id now targets BioInsights (FULL sorts first in validateEmrIntegration findFirst desc); (b) kits_options=2 unconfirmed; (c) JAG payment method for EMR ordering unverified.

## Open items (go-live checklist)
1. ~~BLOCKER: provision account permissions~~ DONE 2026-07-23 (Serdar). Remaining vendor asks: confirm direction convention (incoming/outgoing semantics) + sample HL7 files.
2. Scope unclear: orders inbound only, results outbound only, or bidirectional? Which practices/clinics? (drives ehr_integrations rows — order gate is ehr_integrations LIVE+ordering per VP-16968 cutover)
3. ~~ehr_vendors row~~ DONE 2026-07-23 (id=46, is_public=0 — flip at go-live). ~~sftp_folder_mapping~~ DONE (id=281, cloud). STILL PENDING: ehr_integrations per practice (needs scope from #2).
4. Need sample HL7 files from vendor to decide transformer mapping needs.
5. Move/secure the private key (unencrypted in ~/Downloads); consider filing a VP ticket for tracking.
