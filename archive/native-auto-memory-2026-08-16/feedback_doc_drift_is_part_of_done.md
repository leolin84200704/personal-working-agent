---
name: feedback-doc-drift-is-part-of-done
description: "SEVERE - a behaviour change is not finished until I have re-checked the docs describing it, in BOTH directions; I shipped code that made the doc lie and only found it because Leo asked"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8d79ed9c-df6d-4ef0-bbce-d58e1e48249f
  modified: 2026-08-13T22:35:48.959Z
---

Leo, 2026-08-13, calling it 嚴重錯誤.

**A behaviour change is not done when the PR merges and the ticket closes. It is done when the documentation describing that behaviour has been re-read and still holds.**

Drift runs in two directions and both do the same damage — someone acts on a false statement about the system:

1. **Doc promises what the code does not do.** The whole VP-17685/17686 investigation started here: the page said staging dry-runs and creates no real samples, while it placed real orders with real accession ids. It also listed 500 as a normal, retryable outcome, which taught partners to live with the bug instead of reporting it.
2. **Code changes and the doc is not updated.** I did this three times in one day:
   - Wrote "partial baskets are still placed with the remaining items" in Confluence v18, then shipped PH-860 which reverses it. Caught only because I happened to re-read the page.
   - Shipped PH-853 (cancel rejects both identifiers) and left the doc telling partners *"if both are sent, placerId wins"* — the exact behaviour PH-853 removed **because it cancelled the wrong order and returned success**.
   - Shipped PH-861 and never added `INVALID_FIELD_TYPE` to the documented error-code list.

For the last two I wrote thorough PR bodies and Jira descriptions and still never opened the doc. It surfaced only when Leo asked "內部 doc 要改嗎?".

**How to apply — closing checklist for any behaviour change:**

- Before calling it done, grep the doc for the behaviour just changed, plus the response/error-contract sections it touches. Do not rely on memory of what the doc says — fetch and search it.
- When the doc stated the old behaviour, **say so explicitly** — "an earlier version of this page said X; that was true when written and is no longer" — instead of silently overwriting. Anyone who read the old version needs to know their understanding changed.
- New error codes, new reasons, new status values: every one is a doc edit, not just a code change.
- Still never document behaviour that is not deployed yet. Correcting drift does not license writing ahead of the code — that is direction 1 all over again.

Related: [[feedback-never-500-for-caller-actionable-failures]], [[feedback-audit-recently-done-tickets]], [[feedback-verify-deploy-with-two-signals]]
