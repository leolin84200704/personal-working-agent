# VP-17810 — follow-up reply draft (2026-08-20, after requester's second question)

Requester (Zendesk side; this message is not in the Jira comments) asked two things:
(a) both patients have pre-existing Vibrant accounts, so use the address already on
file rather than adding it manually from the order; (b) can the address auto-populate
from the Cerbo order in future so the manual step goes away.

Jira itself was moved to Done 2026-08-20 13:09 PDT.

## Draft comment (English, for Leo to review before posting)

Thanks for the follow-up.

Both patients exist in our system, but neither profile had an address on file, so
there was nothing for us to use. We have saved the address from the Cerbo order files
(108 Woodland Rd, Kentfield, CA 94904) to both patient profiles. If that is not the
address you expect for either patient, send us the correct one and we will update it.

For future orders, an EMR order does not update an existing patient's profile, so the
address in the order file will not fill in automatically. If you would like it to,
please raise it as a feature request with the PM and we will scope it.

## Evidence backing the draft (verified 2026-08-20, prod)

- `lis_core_v7.patient`: 3055218 HENRI GATTO (DOB 2023-08-28), 3163501 LAURA HENMAN
  (DOB 1983-04-03), both `customer_id=10806`, `user_id` NULL, `original_patient_id`
  NULL. Name+DOB search across the whole patient table returns exactly these two
  rows — no duplicate/older profile carrying a real address anywhere.
- `lis_core_v7.address`: rows 4544741 / 4690151 are the only address rows for these
  patients; both now `108 Woodland Rd / Kentfield / CA / 94904 / US`, `shipping`,
  `address_confirmed=1` (all fields were blank before the 2026-08-20 fix).
- `lis_core_v7.order_info` for both patients — 6 orders, all `address_id` NULL:
  | order_id | patient | source | status | kit status | missing-info |
  |---|---|---|---|---|---|
  | 11154121 | 3055218 | BillingSpring | completed | kit_lab_received | no |
  | 11311292 | 3163501 | BillingSpring | completed | kit_lab_received | no |
  | 11435986 | 3163501 | BillingSpring | completed | kit_lab_received | no |
  | 11447734 | 3055218 | BillingSpring | completed | kit_lab_received | no |
  | 11466683 | 3055218 | EMR | received | kit_ready_for_shipment | no |
  | 11466684 | 3163501 | EMR | received | kit_ready_for_shipment | missing_info_issue |
- `order_info.address_id` is NULL for **all 12,713 orders created since 2026-08-01**
  (NewOrder 10038, BillingSpring 2367, WP 163, EMR 145) — de-facto abandoned column,
  so downstream resolves the address from the patient profile, i.e. the row we fixed.

## Deliberately NOT in the customer reply (observations, no action claimed)

- Order 11466684 still carries `missing_info_issue`. Mechanism: coreSamples
  `processor/sample_processor.go:1320` sets it from issue types 94/100/101 (and
  60/64), and `lis_frontend_service.issue_display` id 14 maps "Missing Address Issue"
  → display "Missing Information". **Which issue this order actually carries is
  unverified** — the issue records are not in any schema our accounts can read
  (`lis_core_v7`, `lis_emr`, `lis_frontend_service`). No evidence it needs us, and
  no evidence it does or does not clear as the order progresses.
- The two 8/19 requisitions were rendered at placement (`AsyncServicesImpl.java:376`
  → old LIS `/orderinfo/SubmitRequisitionFormHandler/NewOrdering`, patient info from
  `OrderServiceImpl.callOldLisOrder` → `buildCompletePatientInfoMap`), so they were
  built from the then-empty profile. The requester did not ask about regenerating
  them, and the substantive problem (the lab having the address) is fixed, so this is
  not offered. Also unverified: whether the portal regenerates a requisition on view,
  and whether kit shipping reads the profile at ship time or a placement snapshot.
