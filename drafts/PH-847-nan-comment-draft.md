# PH-847 — draft Jira comment for Nan (NOT POSTED)

> Target: PH-847. Audience: Nan Wu (reporter/PM, api-product).
> Purpose: get sign-off on taxonomy direction + scope + rollout before opening
> the implementation ticket. Drafted 2026-08-31, awaiting Leo approval.

---

Dug into where the divergence actually comes from, and a proposal below.

**Root cause.** Both endpoints call the same order-management eligibility-check
API and pass its `failures[].code` through verbatim (PascalCase:
`PatientNotFound`, `GeneticTestAlreadyOrdered`, ...). The order endpoint
additionally has its own pre-eligibility validation layer that emits snake_case
reasons (`patient_not_found`, `unrecognized_test_codes`, ...). So a missing
patient surfaces as `PatientNotFound` on quote (caught by the eligibility
check) but `patient_not_found` on order (caught by our own layer first) — same
fact, different layer, different code. The order endpoint is even inconsistent
with itself: `rejected` responses use snake_case, `ineligible` responses leak
PascalCase.

**Proposal — one vocabulary, one carrier:**

1. **snake_case is canonical.** It is what the shipped, documented order
   contract already uses (statuses, rejection reasons, cancellation reasons).
   Both services normalize the eligibility pass-through mechanically
   (`PFSAMaleOnly` → `pfsa_male_only`); no hand-maintained mapping table, so a
   new upstream code converts identically on both sides with no sync risk. The
   human-readable `reason` text stays verbatim.

2. **`failures[{code, reason}]` becomes the uniform failure carrier on both
   endpoints.** Additive on order: `rejected` responses keep `reason` /
   `errorCodes` unchanged and additionally carry `failures[]` in the same shape
   `ineligible` already uses. On quote, the unrecognized-testCodes case moves
   from a prose 400 into the outcome: `{eligible:false, failures:[{code:
   "unrecognized_test_codes", ...}], errorCodes:[...]}` — same code and same
   companion field as order. Net effect: a partner writes one handler — "on
   failure, switch on `failures[].code`" — and it works on both endpoints.

3. **HTTP semantics unchanged.** Quote keeps answering ineligibility at 200
   (`eligible:false` is a successful answer to "can this be ordered?"), order
   keeps 422 (the place-order action failed). With a shared vocabulary in the
   body this difference no longer forces endpoint-specific client logic; we
   document the rationale.

4. **Optional scope extension — your call.** Quote's request-level errors
   (missing patientId, bad payload, upstream down) are still prose
   `{"error": "..."}` with no machine code and no request id — the same support
   black hole we fixed on the order side (error envelope + `x-request-id`).
   Porting that envelope to quote is small (few error paths) and would complete
   the alignment, but it goes beyond this ticket's literal scope. Include it?

**Breaking-change surface + rollout.** The only breaking part is the
`failures[].code` casing flip (quote ineligible + order ineligible), affecting
the current beta-scale integrators. The docs already announce that reason codes
are being unified and instruct clients to fall back to the human-readable
`reason` on unknown codes, so spec-compliant clients survive the flip. Proposed
rollout: update the docs first (single reason table both endpoints reference,
per-endpoint applicability noted), notify partners, flip sandbox, short soak,
then prod. No dual-emit — not worth the long-lived debt at this integration
scale.

Two doc fixes to fold in regardless: the quote 400 today sends `unknown_codes`
while the docs say `unknownCodes`; and the eligibility failure list should be
re-published in snake_case as the canonical table.

If this direction works for you, could you open the implementation ticket(s)?
The work splits into one change in pricing (quote), one in lis-backend-emr-v2
(order), plus the mintlify updates — happy to pick them up once created.
