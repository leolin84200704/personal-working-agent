# VP-17760 — Jira comment draft (EN, for Leo to review/post)

> Target: VP-17760, addressed to Nan Wu (reporter) + api-product.
> Context: implementation PR is up; two things need their side.

---

Unblocked and implemented — the missing piece, a read-only cancellation
pre-check, shipped today as order-management's `GET /orders/cancellation-preview`
(documented on the Cancel Order API Confluence page, section 2). PR #386
(draft, → staging) implements `GET /orders` as documented: lookup by exactly
one of `orderId` / `placerId`, with `status`, `kit` (status + tracking
number), `lab`, `report` (status + the two counts), `cancellation`
(cancellable / fee / reason), and `exceptions`.

Two items need a decision/action outside this repo:

**1. Pre-placement statuses (contract addition — needs a mintlify update).**
The documented enum starts at `placed`, but the recovery scenario this ticket
exists for happens BEFORE `placed`: a caller times out, polls, and the order
is still mid-placement — or placement failed. Answering 404 there sends the
caller straight back to the blind re-POST this endpoint was built to replace,
and for a row stranded mid-placement (pod death) the caller would loop on
GET→404 / re-POST→duplicate forever with no way out. So for the caller's OWN
orders, the lookup also returns:

* `processing` — placement still in flight (or stranded; retry the GET, or
  re-POST the same placerId later)
* `rejected` — the request was rejected (fix and re-POST the same placerId;
  it is reclaimable)
* `failed` — our pipeline failed (re-POST the same placerId)
* `dry_run` — the row was placed while the integration ran in dryrun mode

These are visible only to the owning customer — cross-tenant/unknown ids
still answer a uniform 404. Please add the four values to the `status` enum
in the API docs (and drop the five fields we agreed on 13 Aug: kit.shippedAt
/ kit.deliveredAt / kit.carrier / report.availableAt / exceptions[].raisedAt —
the docs still show them).

**2. Gateway route confirmation (api-product).** The docs promise
`GET /orders?orderId=...` — a base-path GET with a query string. The verified
gateway behavior covers `POST /v1/orders` and the `/v1/orders/*` subpath
passthrough; whether the base-path route forwards GET with the query string
intact is unverified. The service binds both shapes, so either works the
moment the gateway does:

* preferred: route `GET /v1/orders` → `GET /api/v1/order-intake` (query string
  preserved)
* already-proven fallback: `GET /v1/orders/status` rides the existing subpath
  passthrough

Please confirm which one the gateway will support so the docs can state it.

One mapping note, as proposed on 13 Aug and now implemented: a *preliminary*
report reports `status: analyzing`, not `report_available` — flipping early
would stop customers polling before the final report exists; partial
availability stays visible via `report.generatedReportCount` vs
`totalReportCount`.
