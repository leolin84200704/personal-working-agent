---
date: 2026-07-14
slug: payment-chain-closeout
related:
- VP-17286
- VP-17408
- VP-17411
distilled: true
---

# Payment-chain close-out + the stacked-PR trap

Continuation of the VP-17286/17407/17408 arc. Today: landed the stranded #259 fixes,
formalized the API payment rule, filed VP-17411, and shipped the incomplete-charge guard.

## The stacked-PR trap (burned once, documented)
#259 was opened with base = parent feature branch while #258 was open. Leo merged
parent-first; GitHub does NOT retarget an open child PR unless the base branch is
deleted — #259 merged INTO THE FEATURE BRANCH and staging silently lacked the fixes.
Caught only because I re-verified `git log origin/staging` after "done and merged".
Rescue PR #261. Rule going forward: stacked PRs merge child-first, or delete the parent
branch on merge; ALWAYS verify origin/staging after a merge round — PR state MERGED is
not "on staging".

## Leo's question that found a bug
"修改的部分只有API嗎?" forced a precise re-answer: the RULE (customerPay must pay) is
API-only, but #255 lives in the shared charge block. Walking that seam exposed that a
stripe 2xx `requires_confirmation` response (empty payment_id) took the finalizer's
success branch (`!errorMessage`), making post-#255 unpaid HL7 orders LESS visible than
before (no fail reason, plus it consumed the unconfirmed intent's sample id). Fix #264:
success requires payment_transaction_id. Lesson: when a shared code path changes, walk
every caller's failure-visibility semantics, not just the happy path — and "does this
change affect only X?" questions from the human deserve a re-derivation, not a recall.

## Requirement formalization pattern
Leo stated the API payment rule in chat (patientPayLater no-card OK; customerPay must
pay or error). Implementation already matched — the deliverable was a pair of regression
tests (#263) + confirming the doc already said it. Cheap, and the rule is now enforceable.

## Tickets filed this arc
VP-17407 (test infra, done), VP-17408 (spec modernization, done incl 3 findings fixes),
VP-17411 (prod unpaid-customerPay umbrella: 3 MDHQ recoveries, charging off-session +
ACH deps, prod release, HL7 alerting decision — open, non-code items remain).

## VP Jira Bug createmeta gotcha (reconfirmed)
Bug requires Environment/Impact/Portal-Affected-System(=EMR)/Detection-Method/duedate;
priority names are "P0 - Highest".."P4 - Lowest"; Portal field is single-select object.
