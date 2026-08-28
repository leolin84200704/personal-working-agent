# VP-17760 — Jira comment draft (EN, for Leo to review/post)

> Target: VP-17760, addressed to Nan Wu (reporter) + order team (Fangyuan
> Yang) + api-product. Revised 2026-08-28 after staging E2E: gateway question
> answered itself (works); the new item is that the documented Cancellation
> Preview is not actually deployed.

---

`GET /orders` is implemented, merged to staging, and verified end-to-end —
including through the external gateway: both the documented
`GET /v1/orders?orderId=|placerId=` (base path, query string intact) and
`GET /v1/orders/status` work with a client-credentials token, so no gateway
change is needed. Full lookup verified: place → poll (`processing` while
placement is in flight, then `placed`), lookup by the returned `orderId` or
by `placerId`, cancel → `cancelled` with `reason: already_cancelled`,
uniform 404 for unknown/cross-tenant ids.

Three items for other owners:

**1. Order team — the documented Cancellation Preview is not deployed.**
The Confluence page (Cancel Order API §2) documents
`GET /orders/cancellation-preview` returning `is_cancellable` /
`not_cancellable_reason`. The live endpoint on BOTH staging and prod
currently answers 200 with the legacy billing-summary shape instead:
`is_refundable`, and no cancellability fields (verified 2026-08-28 with raw
probes; note a cancelled order answers `is_refundable: true`, so
`is_refundable` cannot stand in for cancellability). Our side detects the
legacy shape and reports `cancellation: null` (unknown) — the moment the
documented response deploys, the block lights up with no change needed from
us. Please share the deploy timeline.

**2. api-product — mintlify updates.** (a) Add the four pre-placement
statuses to the `status` enum: `processing`, `rejected`, `failed`,
`dry_run` — returned only for the caller's own orders whose placement has
not (yet) completed; hiding them behind 404 would strand a caller whose
placement died mid-flight (GET→404 / re-POST→duplicate forever). (b) Drop
the five fields agreed on 13 Aug (kit.shippedAt / kit.deliveredAt /
kit.carrier / report.availableAt / exceptions[].raisedAt) — the docs still
show them. (c) `cancellation` may be `null` while item 1 is pending.

**3. FYI, mapping note now live:** a *preliminary* report reports
`status: analyzing`, not `report_available` — flipping early would stop
customers polling before the final report exists; partial availability stays
visible via `report.generatedReportCount` vs `totalReportCount`.

Known limitation (documented): `orderId` exists only for orders placed after
13 Aug (PH-855); older orders are identified by `placerId`.
