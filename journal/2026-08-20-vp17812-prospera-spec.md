---
date: 2026-08-20
slug: vp17812-prospera-spec
related:
- VP-17812
- QH-6764
- VP-16245
- VP-16987
- VP-17475
- BIOINSIGHTS-onboarding
distilled: true
---

# 2026-08-20 — VP-17812 Prospera integration spec

Related: VP-17812, QH-6764, VP-16245, VP-16987, VP-17475, BIOINSIGHTS-onboarding

## What happened
- New ticket VP-17812 (2026-08-19): provide technical specifications to EMR vendor
  Prospera (contact Robin) for 5 areas of a "remaining" bi-directional integration.
  Ticket asserted an existing SFTP/HL7 workflow and that 4/5 requirements were already
  supported.
- Verified every claim before writing anything vendor-facing. Ground truth diverged:
  - Prospera has ZERO presence in prod lis_emr (all 31 ehr_vendors checked, plus
    ehr_integrations / order_clients / sftp_folder_mapping / hl7_file_input) and zero
    Jira history beyond this ticket → new vendor from our side.
  - Requisition form (#2): no vendor-facing mechanism exists anywhere (emr-v2 pushes
    only the ORU; LIS-transformer endpoints are internal-JWT + private-IP scanned-req
    proxy; order-management has no REQUISITION_PDF type).
  - Practice contact (#4): mechanically fine (PID-20.1 email / PID-13.1 phone) but every
    order overwrites the patient's stored contact record (updateContactIfChanged).
  - Kit options (#5): per-practice kits_options only; no per-order HL7 field.
- Two Explore agents produced the full inbound/outbound mechanics (billing IN1-2.1='C'
  → customerPay; ORM envelope + dedup rules; ORU shape with base64 PDF OBX; onboarding
  surface incl. sftp_private_key support). Details in STM VP-17812.
- Wrote vendor spec v1.0: undecided items phrased as "being finalized" + open questions
  back to Prospera (incl. asking THEM which practices already exchange data — resolves
  the existing-integration contradiction from their side without accusing the ticket).

## Decisions / user words
- Leo (2026-08-20): 「我找不到md 檔。另外寫成 artifact 客戶看不到也沒用。請你給我doc
  就可以」 → customer-facing deliverables must be a .docx file (pandoc gfm→docx), placed
  somewhere findable (~/Desktop). Artifacts are for Leo-internal review at best; do not
  treat an artifact as delivery for external parties.
- Leo then confirmed "done". Ticket stays open awaiting Robin/Prospera answers.

## Explored and excluded
- Searched for Prospera under alternate identities (clinic_name, practice name,
  requested_by, hl7 file paths) — nothing. Did not guess a mapping to an existing vendor
  code; put the question to Prospera instead.
- /quote endpoint from VP-17475-era memory: does not exist anywhere in current repos.
- Test images: confirmed absent across catalog models (only kit/tube images in
  LIS-Sample inventory assets) — spec states this plainly.

## Incidental findings (recorded, not actioned)
- Both SFTP connection-test endpoints (ehr-vendor.controller.ts:266-293,
  configuration-management.controller.ts:191+) pass only sftp_password, never
  sftp_private_key → key-only vendors fail the connectivity test though real fetch/push
  work. Reported to Leo; no ticket yet (owner-qualification rule).

## Artifacts
- drafts/VP-17812-prospera-integration-spec-v1.md (vendor version, source of the docx)
- drafts/VP-17812-prospera-integration-spec-draft.md (internal, [INTERNAL] markers)
- ~/Desktop/VP-17812-Prospera-Integration-Spec-v1.docx (delivered)
- lis-backend-emr-v2/scripts/_probe-prospera-vp17812.ts (read-only prod probe)
