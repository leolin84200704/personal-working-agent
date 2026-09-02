# Vibrant America — SFTP/HL7 Bi-Directional Integration: Technical Specification (DRAFT for Prospera)

> DRAFT v0.1 — 2026-08-19, prepared for VP-17812. Verified against lis-backend-emr-v2
> @ origin/main (ebb104f). Items marked **[INTERNAL]** are for Leo's review and must be
> resolved/removed before sending to Robin/Prospera.

---

## 0. Transport and message envelope

**Orders (Prospera → Vibrant), over SFTP:**
- Vibrant polls the agreed SFTP order folder **every 15 minutes** and picks up files with
  extension `.hl7` / `.HL7` only.
- After pickup, the file is **moved to an `archive/` subfolder inside the pickup folder**
  (created automatically).
- **Filenames must be unique per folder.** A file with a name that was already ingested
  from the same folder is silently ignored — resends must use a new filename.
  Recommended convention: `{orderId}_{YYYYMMDDHHMMSS}.hl7`.
- Message type: **ORM^O01** (OML^O21 is accepted and normalized). HL7 v2.3.
  Pipe-delimited, encoding chars `^~\&`. Segment terminator `\r`, `\n`, or `\r\n`.
- **MSH-10 (Message Control ID) must be unique per order.** A duplicate control ID is
  treated as a resend of the same order and short-circuits to the previously created
  sample (nothing new is placed or charged).
- One bad test code rejects the **entire message** — there is no partial order placement.
  Rejected orders are retried automatically for a limited number of attempts (useful when
  the failure is a missing configuration on Vibrant's side).

**Required segments and key fields (inbound order):**

| Segment/Field | Content |
|---|---|
| MSH-9 | `ORM^O01` |
| MSH-10 | Unique message control ID |
| PID-2.1 | Patient external ID (Prospera's patient identifier) |
| PID-5 | Patient name `Last^First` |
| PID-7 | DOB `YYYYMMDD` (required) |
| PID-8 | Sex `M`/`F` (required) |
| PID-11 | Patient address `street^^city^state^zip` |
| PID-13.1 | Contact phone (digits; see §4) |
| **PID-20.1** | **Contact email** — Vibrant's convention places email in PID-20, **not** PID-13.4 |
| ORC-2.1 | Placer order number (echoed back on results as ORC-2 / OBR-2) |
| **ORC-12.1** | **Ordering provider: Vibrant Provider ID (≤7 digits) or 10-digit NPI** — this is the routing key; provider must be onboarded with Vibrant first |
| OBR-4.1 | Test code (see §3) |
| OBR-7.1 | Collection date-time `YYYYMMDDHHMM` (defaults to receipt time if empty) |
| IN1-2.1 | Billing indicator (see §1) |

---

## 1. Vibrant billing — charge the card on file

Supported today. The billing mode is selected **per order** via the first IN1 segment:

- **IN1-2.1 = `C`** (uppercase, exactly): **practice-pay** — Vibrant charges the payment
  method(s) on file for the ordering provider/practice. The patient is not asked to pay
  and receives no payment email. **This is the value Prospera should always send.**
- Any other value, or no IN1 segment at all: **patient-pay-later** — Vibrant emails the
  patient a payment link to the contact email on the order. (Not what Prospera wants;
  included for completeness.)

Prerequisite: the practice must have a card on file with Vibrant (set up once through
Vibrant; not part of the HL7 flow).

**[INTERNAL]** On the HL7 path a failed card charge does NOT block order placement — the
order proceeds with `emr_payment_fail_reason` recorded (VP-17411 revenue-leak history).
Decide whether to mention dunning/failure handling to Prospera, and whether we want a
blocking behavior for this vendor.

---

## 2. Requisition form — **[INTERNAL — currently NOT available; decision needed]**

Ticket claims "supported" but **no vendor-facing requisition mechanism exists**:
- emr-v2 pushes exactly one artifact to vendor SFTP: the result ORU file. No requisition
  push anywhere.
- The only requisition PDF endpoints are internal JWT-gated LIS-transformer routes
  (`/trans/getRequisitionForm?sample_id=`) proxying a **private-IP legacy host**
  (`192.168.60.77:8081/secure/nologin/FetchScannedRequisition`) that serves *scanned*
  requisitions, not generated forms.
- order-management's PDF service has no REQUISITION_PDF type (only ORDER_SUMMARY,
  BLOOD_DRAW, NY_FORM, COLLECTION_INSTRUCTION, SHIPPING_INSTRUCTION, WELCOME_LETTER,
  PRECOLLECTION_INSTRUCTION).

Options to make it real: (a) emr-v2 pushes a requisition PDF alongside/after order intake
to a vendor SFTP folder; (b) expose a token-gated download URL per order; (c) add a
REQUISITION_PDF type in order-management and wrap it. All are new development — needs
scoping before promising anything to Prospera.

---

## 3. Vibrant test menu

**Test code formats accepted in OBR-4.1** (whitespace is stripped; one OBR per test):

| Format | Meaning | Notes |
|---|---|---|
| `VAREQUISTION{id}` | Standard panel/package (global catalog) | Spelling is REQUIS**T**ION (one I). Case-insensitive match |
| `VATEST{id}` | Single test | Case-insensitive match |
| `VACP{id}` | Customer-specific custom bundle | **Case-sensitive** (`VACP` uppercase); scoped to the ordering customer/clinic |
| bare number | Same as VACP custom bundle | |

- A code must exist in Vibrant's catalog **and be flagged orderable**; otherwise the whole
  order is rejected (auto-retried; recovers once the catalog is fixed).
- **Test images: not available.** Vibrant's catalog carries code, name, and price only —
  no per-test images exist in any Vibrant system (only specimen kit/tube images).
- Favoriting/commonly-used lists are a Prospera-side UX feature; nothing needed from
  Vibrant beyond the menu data.

**[INTERNAL — delivery method undecided]** There is **no vendor-facing catalog API**.
All pricing/catalog endpoints are behind Vibrant's internal JWT (shared-secret; no
partner auth model). The 2026-06-17 huddle conclusion was that emr-v2 must not become the
catalog publisher — the per-customer orderable catalog belongs upstream (pricing/portal).
Practical near-term options:
1. Send Prospera a **static export** (code, name, price) generated from
   `getLegacyPackagePriceMapping` (+ per-customer `getLegacyBundleMapping` for VACP),
   refreshed on an agreed cadence;
2. **Scheduled SFTP CSV drop** — scheduled-reports precedent exists (VP-16987 quarterly
   client CSV);
3. Ask the upstream catalog team for a partner-facing API (long-term correct answer).

---

## 4. Practice contact information instead of patient's

Mechanically supported today: the contact email and phone on an order are taken from
**PID-20.1 (email)** and **PID-13.1 (phone)** per message, and no validation prevents
Prospera from populating them with the practice location's email/phone for selected
orders. Lab communications for that order (including a patient payment email, if ever
applicable) then go to the practice.

**[INTERNAL — side effect needs a product decision before we bless this]**: inbound
PID-13/PID-20 values **overwrite the stored patient contact record** in Vibrant's patient
DB on every order (`updateContactIfChanged` → gRPC UpdatePatientInfo). If a practice
sends its own contact info for many patients, all those patient records converge to the
practice's email/phone — affecting every other Vibrant touchpoint for those patients
(portal notifications, etc.). Options: accept as-is; or add a per-integration flag to
skip the patient-record write-back; or have Prospera send practice contact only when
truly needed. Needs a ruling before the spec promises this pattern.

---

## 5. Kit / collection options

Supported today as **per-practice configuration** (`kits_options` on the integration),
not per order:

| Option | Non-blood kits | Blood collection supplies | Matches Prospera's ask |
|---|---|---|---|
| 0 | Shipped to patient's home | Stocked at the clinic | Mixed |
| 1 | Shipped to patient's home | Shipped to patient's home | "Kit shipped to patient's home for finger-stick collection" |
| 2 | Stocked at the clinic | Stocked at the clinic | "Collection performed at the clinic" |

- Each connected practice picks one option at onboarding; it applies to all its orders.
- **[INTERNAL]** There is **no per-order HL7 field** for collection choice — if Prospera
  needs order-by-order selection (their wording "support the appropriate collection
  option, including both" suggests they might), that is new development (new HL7 field
  convention + parser change). Clarify with Robin whether per-practice granularity is
  acceptable.

---

## 6. Results delivery (Vibrant → Prospera)

- **ORU^R01**, HL7 v2.3, one file per order (partial-result pushes available as an
  opt-in configuration), uploaded to the agreed results folder on the SFTP.
- Filename: `{placer order id | Vibrant sample id}.hl7`. A repush overwrites the same
  filename.
- MSH-5 = Prospera's vendor code (assigned at onboarding); MSH-6 = per-practice
  receiving-facility ID (Vibrant Practice ID by current convention).
- ORC-2/OBR-2 echo Prospera's placer order number from the inbound ORC-2.1.
- OBR-4 = `{test code}^{panel name}` (same code space as §3).
- OBX segments carry numeric/string results with units, reference range, and abnormal
  flags; NTE carries not-processed/no-reference-range notes.
- **PDF report is embedded in the HL7** as the final OBR/OBX group:
  `OBX|1|ED|PDF^PDF||^AP^^Base64^{base64 PDF}` — no separate PDF file is uploaded.
  Report style (classic/personalized) and whether to embed at all are per-practice
  configuration.
- **No HL7 ACK/MSA handshake** — Vibrant neither sends nor expects acknowledgements.

---

## 7. Onboarding data Vibrant needs from Prospera

1. Vendor identity: name + short code (becomes MSH-5 on results).
2. SFTP endpoint: host, port, username, **password or SSH private key (key preferred;
   PEM/OpenSSH format)** — or use Vibrant's shared SFTP if Prospera prefers to poll.
3. Folder layout: orders path, results path (archive handled by Vibrant under the
   orders path).
4. Supported HL7 version(s) — default 2.3.
5. Per connected practice: Vibrant Practice ID + roster of ordering providers
   (Vibrant Provider IDs / NPIs — each provider must be onboarded before ordering),
   receiving-facility value for MSH-6, report style (classic/personalized, PDF embed
   yes/no), kit/collection option (§5), result push granularity (whole-order default).
6. Card on file per practice for §1 billing.

**[INTERNAL]** If Prospera goes key-auth: both SFTP connection-test endpoints
(ehr-vendor.controller.ts:266-293, configuration-management.controller.ts:191+) only
pass `sftp_password`, never `sftp_private_key` — key-only vendors fail the connectivity
test even though real fetch/push work (BIOINSIGHTS precedent). Worth a small fix ticket.
