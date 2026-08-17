---
name: feedback-never-500-for-caller-actionable-failures
description: "A 500 for a condition the caller caused or could act on is a defect in itself — return 4xx with a machine-readable reason in the caller's own vocabulary, and never let an upstream drop stay silent"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8d79ed9c-df6d-4ef0-bbce-d58e1e48249f
  modified: 2026-08-12T20:03:32.565Z
---

Leo, 2026-08-12, on VP-17686: 「這是嚴重的錯誤，是你應該要記起來的問題，不能等客戶發現」 and 「再怎麼樣也不該回500，要正確回覆error不是嗎？」

Four rules that came out of one bug:

1. **Never 500 on a caller-actionable condition.** A partner sent a valid order with valid codes and got `{"statusCode":500}`. That says "our system is broken", gives them nothing to quote back, and no way to decide whether to resend. Derived-empty state (the basket priced to nothing) is a *rejection*, not a crash → 422 + `reason` + `errorCodes`.
2. **Answer in the caller's vocabulary.** Returning `errorCodes:["861"]` to someone who sent `"APOE_BLOOD"` is useless. Map internal ids back to what they sent. I shipped the id form first and only caught it in live verification.
3. **Normalise input once at the boundary, never per call site.** A stringified `patient_id` travelled to an upstream that required a number → 400 → surfaced as 500. I first patched the one call site I could see; the real fix is coercing at the controller. Per-call-site patching is exactly how the bug survived that long.
4. **Reconcile sent-vs-returned at every integration boundary, and log the difference.** The upstream accepted every item and silently returned fewer, reporting no error. "No error" ≠ "nothing lost". Without a diff log this took a multi-hour investigation instead of one grep; a customer found it before we did.

**Why:** the discovery path was backwards — an external tester hit it, then a support thread, then me. Everything needed to catch it earlier existed (the response listed exactly what it covered) but nothing compared it.

**How to apply:** when wiring any upstream that takes a list and returns a list, write the reconciliation *at the same time* as the happy path: diff sent vs accounted, log every drop, and convert "nothing survived" into an explicit 4xx. Treat a bare 500 reaching an external caller as a bug to file, independent of whatever upstream caused it.

Related: [[project-bestdeal-silently-drops-addon-tests]], [[feedback-defect-found-must-be-ticketed]]
