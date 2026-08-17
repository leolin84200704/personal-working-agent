---
name: Bundle lookup fallback logic (clinic_id)
description: VP-15302 — correct ordering for customer/clinic bundle fallback with expireTime checks
type: project
originSessionId: e347efec-ad1a-4826-bc5f-1da577b2d0bd
---
The clinic_id fallback in bundle lookup MUST happen after expireTime check, not before.

Correct order:
1. Query by customer_id → found AND not expired → use it
2. Otherwise (not found OR expired) → query by clinic_id → found AND not expired → use it
3. Otherwise → return errorCodes

**Why:** If you fallback first then check expireTime in one unified step, a customer-level bundle that is expired will skip the clinic-level fallback entirely — the code sees "found a bundle" and checks expiry, but never tries clinic-level.

**How to apply:** When modifying bundle lookup logic, ensure each level (customer → clinic) has its own expiry check before falling through to the next level.
