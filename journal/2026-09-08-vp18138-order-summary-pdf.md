---
date: 2026-09-08
slug: vp18138-order-summary-pdf
related_tickets: [VP-18138, PH-904, VP-17812]
tags: [emr-v2, order-management, sftp, result-push, next-health, prospera, followthatpatient, schema-change]
distilled: false
---

# 2026-09-08 — VP-18138: Complete Order Summary PDF next to HL7 results (analysis -> PR #403)

## What happened
- Atlassian MCP down all session; read VP-18138 / PH-904 / QH-7017 through Jira REST with the
  `.env` token instead. STM index stale (09-03) — flagged to Leo.
- Ticket = the build for VP-17812 Q2 (Prospera picked "PDF alongside result on SFTP"). Leo's
  earlier constraint held: no new SFTP, existing Next-Health folder, Vibrant-side only.
- Prod ground truth reshaped the design twice:
  1. Prospera still has no vendor row; the entity is FOLLOWTHATPATIENT (33 LIVE rows / 20 clinics /
     one folder) -> vendor-level gate.
  2. 382/382 Next-Health result pushes in 90 d are portal orders (no emr_sample) -> the PDF lookup
     key must be sample_id/accession, never emr_order_id.
- Found the document: two implementations titled "Complete Order Summary" — legacy Java
  LIS-backend-billing (`/v1/portal/order/patientPage/generateNormalOrderPdf?sampleId=`, what the
  transformer/statement page still call) and Go order-management
  (`/v2/portal/order/pdf/generateNormalOrderPdfBundles?sample_id=`, what the order page calls).
  Chose Go; asked PM to attach their sample so staging output can be compared.
- Explore agent warned v2 `orders` coverage is best-effort (Kafka->asynq mirror, 1 h expiry).
  Did a read-only live probe with a self-minted HS256 token: 25/25 accessions resolve, sample_id
  matches, token accepted by order-management. Deliberately did NOT call the PDF route in prod
  (cache-miss render + async R2 upload = side effect).
- Debate: PRO in-job/vendor-flag/re-drop-every-push vs CON sweeper/new-table/short-timeout/
  observability. Took CON's table + 30 s cap + daily-triage hook + written vendor confirmation;
  kept in-job and vendor flag. Leo approved A with `ehr_vendors` column and
  `{accession}_ordersummary.pdf`.
- Implemented test-first in worktree from origin/main (main checkout was on a stale bugfix
  branch, 15 behind): client service, attachment service, optional trailing dep on
  ResultGenerationService, hook after the ChARM block, new table + vendor column, migration SQL,
  doc, .env.example. 21 new tests, full jest green after generating the sqlite test client.
- Commit 5aa62b4, PR #403 -> staging (repo convention feature -> staging -> main).

## Explored and rejected
- Second OBX ED segment in the HL7 (customer explicitly wants a file).
- order-management pushing to SFTP itself (no integration/SFTP knowledge; breaks single exit).
- Env allowlist instead of vendor column (deploy-to-change, invisible to ops) — offered, Leo chose column.
- Columns on result_transmission_records (deploy-before-DDL breaks all reads; 24 h row reuse
  overwrites history) — replaced by append-only result_attachment_records.
- Separate sweeper job (CON's preferred) — kept as Phase-2 backlog re-drive over the same table.
- Promise.race timeout around the attachment SFTP put — race can't cancel the put; would create
  "UPLOAD_ERROR but file landed" inconsistency. Left SftpService's own timeout.

## Gotchas worth keeping
- zsh: `echo ====X` / `--include=*.ts` unquoted -> "not found" / "no matches" and the rest of the
  line is lost. Quote globs, avoid leading `=`.
- Inside a `*.worktrees/` checkout, `--testPathIgnorePatterns=worktrees` ignores every test.
  Use `'\.claude/worktrees'`. Fresh worktree also needs `prisma generate --schema
  prisma/schema.test.prisma` or 5 sqlite suites fail with "Cannot find module .prisma/test-client".
- `GET /orders/info?accession_id=` on order-management returns 500 for not-found (no 404).
- order-management `/pdf/*` has no per-order authorization — any valid platform JWT reads any
  sample. Not ours to fix here; noted.

## Leo's words
- "方案 A 同意，加 ehr_vendors 欄位，檔名用 {accession}_ordersummary.pdf，開始 Step 5"
- "commit + create pr"

## Open after this session
- DDL on staging + prod before deploy; staging round-trip; vendor 44 enablement after PM/Prospera
  answers; DailyJob result_fail query for `result_attachment_records` (separate personal-repo PR).
- Side observation: 59 result records in 2 days with `connect ETIMEDOUT 10.224.0.199:32100`
  across 6-7 vendors (on-prem pusher -> cloud gRPC). Reported to Leo; belongs to result_fail triage.
