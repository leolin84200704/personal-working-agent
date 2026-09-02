# Vibrant America — EMR Integration Technical Specification for Prospera

Version 1.0 (draft for review) — 2026-08-19
Scope: SFTP/HL7 v2 bi-directional integration — order submission, billing, test menu, practice contact handling, kit/collection options, and result delivery.

---

## 1. Transport overview

- Exchange is over SFTP. Vibrant can poll a Prospera-hosted SFTP server, or host folders on Vibrant's shared SFTP — either works; credentials and folder layout are agreed at onboarding.
- Authentication: username + password, or SSH key (PEM/OpenSSH private key). Key-based auth is preferred.
- **Orders (Prospera → Vibrant):** Vibrant polls the agreed orders folder **every 15 minutes** and ingests files with extension `.hl7` / `.HL7` only. After successful pickup, the file is moved to an `archive/` subfolder inside the orders folder (created automatically by Vibrant).
- **Results (Vibrant → Prospera):** Vibrant uploads one HL7 result file per order to the agreed results folder (details in §8).

### File naming rules (orders)

- Filenames must be **unique per folder, forever**. A filename that was already ingested from the same folder is silently ignored — a resend must use a new filename.
- Recommended convention: `{orderId}_{YYYYMMDDHHMMSS}.hl7`.

## 2. Order message envelope

- Message type **ORM^O01** (OML^O21 is also accepted), HL7 **v2.3**, pipe-delimited, encoding characters `^~\&`. Segment terminators `\r`, `\n`, or `\r\n` are all accepted.
- **MSH-10 (Message Control ID) must be unique per order.** A message whose control ID was seen before is treated as a resend of that same order: it maps to the previously created Vibrant sample, and no new order is placed or charged. To submit a new order, always use a fresh MSH-10.
- One order per file is recommended.

### Key fields

| Field | Content | Notes |
|---|---|---|
| MSH-9 | `ORM^O01` | |
| MSH-10 | Unique message control ID | Dedup key — see above |
| MSH-12 | `2.3` | |
| PID-2.1 | Prospera's patient identifier | Used to match/create the patient on Vibrant's side |
| PID-5 | Patient name `Last^First` | Required |
| PID-7 | Date of birth `YYYYMMDD` | Required |
| PID-8 | Sex `M` / `F` | Required |
| PID-11 | Patient address `street^^city^state^zip` | |
| PID-13.1 | Contact phone (digits) | See §5 |
| **PID-20.1** | **Contact email** | Vibrant's convention carries email in **PID-20**, not PID-13.4 — see §5 |
| ORC-2.1 | Placer order number | Echoed back on results (ORC-2 / OBR-2) |
| **ORC-12.1** | **Ordering provider: Vibrant Provider ID (≤ 7 digits) or 10-digit NPI** | Routing key. The provider must be onboarded with Vibrant before ordering |
| OBR-4.1 | Test code | One OBR per test — see §4 |
| OBR-7.1 | Collection date-time `YYYYMMDDHHMM` | Defaults to receipt time if empty |
| IN1-2 (component 1) | Billing indicator | See §3 |
| DG1-3 | ICD diagnosis codes | Optional |

### Sample order message

```
MSH|^~\&|PROSPERA|{PracticeID}|Laboratory|Vibrant America|20260819120000||ORM^O01|PRSP20260819120000001|P|2.3
PID|1|PRSP-12345|||Doe^Jane||19850214|F|||123 Main St^^San Carlos^CA^94070||6505551234|||||||frontdesk@examplepractice.com
ORC|NW|PRSP-ORD-1001||||||||||1234567^Smith^John
OBR|1|PRSP-ORD-1001||VAREQUISTION463^Gut Zoomer 5.0|||202608190930
IN1|1|C
```

### Rejection and retry behavior

- An unrecognized or non-orderable test code rejects the **entire message** — there is no partial order placement.
- Rejected messages are retried automatically by Vibrant for a limited number of attempts (roughly the following hour), so failures caused by missing configuration on Vibrant's side (e.g. a provider not yet onboarded) recover without a resend once fixed.
- Persistent failures are surfaced to Vibrant's integration team; we will coordinate through the agreed support channel.

## 3. Billing — Vibrant charges the card on file (Requirement 1)

The billing mode is selected **per order** through the first IN1 segment:

- **IN1-2 component 1 = `C`** (uppercase, exactly): **practice-pay.** Vibrant charges the payment method on file for the ordering practice/provider. The patient is not asked to pay and receives no payment email. **Prospera should send `C` on every order.**
- Any other value, or omitting the IN1 segment entirely, selects patient-pay: Vibrant emails the patient (at the order's contact email) a payment link. This is documented for completeness only — it is not the mode Prospera has requested.

Prerequisite: each practice must have a payment method on file with Vibrant. This is set up once with Vibrant outside the HL7 flow (part of practice onboarding).

## 4. Test menu (Requirement 3)

### Test code formats accepted in OBR-4.1

| Format | Meaning | Notes |
|---|---|---|
| `VAREQUISTION{id}` | Standard panel / package (global catalog) | Note the spelling — REQUIS­TION, one "I" |
| `VATEST{id}` | Single test | |
| `VACP{id}` | Practice-specific custom bundle | `VACP` must be uppercase; valid only for the customer/practice it was created for |

- Whitespace inside the code is ignored. OBR-4.2 may carry the display name; it is not used for matching.
- A code must exist in Vibrant's catalog and be flagged orderable; otherwise the whole order is rejected (with automatic retry, per §2).

### Test menu data

- Vibrant will provide the orderable test menu (code, name, price) as a data export; the format and refresh cadence are listed as open questions in §9.
- **Test images are not available** — Vibrant's catalog does not carry per-test imagery.
- Favoriting / commonly-used lists are a Prospera-side feature; no additional data is needed from Vibrant beyond the menu itself.

## 5. Practice contact information on orders (Requirement 4)

The contact email and phone for an order are read per message from **PID-20.1 (email)** and **PID-13.1 (phone)**. Prospera may populate these with the practice location's email/phone for orders where lab communications should not go to the patient — no additional flag is needed.

**Important behavior to design around:** the contact details submitted on an order become the patient's contact information of record with Vibrant for that patient (each order updates it). If the practice's contact info is submitted, subsequent Vibrant communications for that patient go to the practice until a later order (or the practice, via Vibrant support) changes it back. Send practice contact details only on orders where the practice intends to intermediate communications.

## 6. Kit / collection options (Requirement 5)

Collection handling is configured **per practice** at onboarding — one of:

| Option | Non-blood kits | Blood collection supplies | Typical use |
|---|---|---|---|
| A | Shipped to patient's home | Stocked at the clinic | Mixed model |
| B | Shipped to patient's home | Shipped to patient's home | At-home collection (e.g. finger-stick kits) |
| C | Stocked at the clinic | Stocked at the clinic | In-clinic collection |

The configured option applies to all orders from that practice. Per-order selection inside the HL7 message is not currently part of the interface; if Prospera requires order-by-order selection, see the open questions in §9.

## 7. Requisition form (Requirement 2)

The delivery mechanism for the Vibrant requisition form through Prospera is being finalized on Vibrant's side. We will follow up with the technical details; §9 includes a question on Prospera's preferred delivery method so we can converge quickly.

## 8. Result delivery (Vibrant → Prospera)

- **ORU^R01**, HL7 v2.3, uploaded to the agreed results folder. One file per order; partial-result delivery ahead of the final report is available as an opt-in configuration.
- Filename: `{placer order id}.hl7` (Prospera's ORC-2.1), falling back to the Vibrant sample ID when no placer id was provided. A re-delivery overwrites the same filename.
- MSH-5 = Prospera's assigned vendor code; MSH-6 = the per-practice receiving-facility ID agreed at onboarding.
- ORC-2 / OBR-2 echo Prospera's placer order number. OBR-4 = `{test code}^{panel name}`, in the same code space as §4.
- OBX segments carry results (numeric or string) with units, reference range, and abnormality flag; NTE segments carry processing notes.
- **The PDF report is embedded inside the HL7 message** as a final OBR/OBX group:
  `OBR|{n}|{placer}|{accession}|VAPDF^Vibrant PDF Report|...|F` followed by
  `OBX|1|ED|PDF^PDF||^AP^^Base64^{base64-encoded PDF}||||||F`.
  No separate PDF file is uploaded. Whether the PDF is embedded, and the report style, are per-practice configuration.
- Vibrant does not send or expect HL7 acknowledgements (ACK/MSA); delivery is file-based.

## 9. Onboarding checklist and open questions

### What Vibrant needs from Prospera

1. Vendor identity: name + short code (appears as MSH-5 on results).
2. SFTP details: who hosts; host/port/username; password or SSH public/private key arrangement; orders and results folder paths.
3. Per connected practice: the practice's Vibrant Practice ID, the roster of ordering providers (Vibrant Provider IDs or NPIs — each provider must be onboarded with Vibrant before ordering), the receiving-facility value for result MSH-6, the report/PDF preference, and the collection option (§6).
4. A payment method on file per practice (§3), arranged with Vibrant outside the HL7 flow.

### Open questions for Prospera

1. **Current state:** which practices (if any) are already exchanging orders/results with Vibrant today, and under what identity? This determines whether we are completing an existing setup or provisioning from scratch.
2. **Requisition form:** what delivery mechanism fits Prospera best — a per-order downloadable link, or a PDF file dropped alongside results on the SFTP?
3. **Collection options:** is the per-practice setting in §6 sufficient, or does Prospera need per-order selection?
4. **Test menu:** preferred format (JSON/CSV) and refresh cadence for the menu export; and does Prospera need practice-specific custom bundles (VACP codes) included per practice?
