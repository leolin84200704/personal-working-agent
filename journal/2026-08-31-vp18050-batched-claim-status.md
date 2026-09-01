---
date: 2026-08-31
slug: vp18050-batched-claim-status
related:
- VP-18050
- VP-18051
- VP-17868
- PH-898
- PH-899
- SIIR-279
- VP-16410
distilled: true
---

# VP-18050 — batched accession claim status for the Select Related Test modal

## What Leo asked
Just the ticket id: `VP-18050`. Later, after the Step 4 proposal: "A, 不需要起草comment, 等做完了再起草。另外 可以先dream". Then after the Step 6 review: "ok, 先不做FE, 可以commit + pr".

## Session start friction
STM/LTM/journal indexes were all stamped 2026-08-26 — 5 days stale, past the 3-day staleness threshold. Cause found in `logs/launchd-stdout-2026-08-{27,28,29,30}.log`: the dream dirty-memory guard aborted four nights running on an uncommitted `storage/short_term_memory/LIS-7716.md`. That file was committed today at 10:39 (68ede38), so the guard was already clear before Leo asked for a manual run. Index scores were treated as untrustworthy for this session; retrieval went through Grep and direct reads instead.

## What was explored, and what was ruled out
The first hypothesis was that the ticket was already satisfied. VP-17868 (merged 2026-08-24, push-to-deploy) added `consultDate` to `isAccessionClaimable`, and the local va-portal branch already consumes it. Against VP-18050's own acceptance criteria that hypothesis holds.

It broke on the sibling ticket. VP-18051 asks for a **row-level** label in the search-result list — "Consult booked", grey, not clickable. That needs claim status for every rendered row *before* the provider clicks any of them, and today `SearchOrders.vue handleClickOrder` only asks about one accession, on click. So the deliverable was real, and it was invisible from VP-18050's text alone.

Ruled out along the way:
- **Doing nothing on the BE.** Satisfies VP-18050's literal AC (the banner date is live) and strands VP-18051.
- **Putting the data in the search response literally.** `loginServiceCloud.post('/trans/findPatient')` is served by **LIS-transformer (v1)**, not transv2 — a different service with no `calendar_prod` access, and it also backs the patient page. Grepping for `findPatient` across the transformer repos is what settled this; it was ~30 seconds and it changed the whole design.
- **Reusing `getClaimedAccessionIds`.** It exists and is bulk, but returns all 3,640 claimed ids for practice 150105, carries no dates, and has zero consumers in va-portal or vibrant-wellness-portal.

## Why the design came out the way it did
The interesting constraint was not performance, it was the disclosure gate. `isClaimable` accepts an arbitrary accession id and never verifies it belongs to the caller's clinic — that is precisely why VP-17868 gated `consultDate` behind "viewer is tied to the holding consult". A batch endpoint over the same data multiplies that exposure, so:
- the gate is applied per row, not per request;
- the batch is capped at 20 with the reason written into the constant's doc comment, so nobody later "tunes" it upward thinking it is a throughput knob;
- `isClaimable` and `claimStatuses` were refactored onto one shared select and one shared row-to-answer mapping, because two copies of a privacy control that silently disagree is the failure mode nobody would notice.

## Verification
41 tests (from 27), including a new `accession-claim.graphql.spec.ts` that boots a real Apollo schema and queries over HTTP. That spec exists for a specific reason: `AccessionClaimStatus extends IsAccessionClaimablePayload`, and code-first GraphQL inheritance is the kind of thing that type-checks and then is simply absent from the schema.

Then a live read-only probe against prod `calendar_prod` through the compiled `dist/` build — 8 real claims plus one fake id: no viewer disclosed zero dates; viewer `user:89268` got dates for exactly the two ids on their own event 13235 and nothing else; batch matched `isClaimable` on all 9 ids; 21 ids were refused; claim count 3,640 before and after. The probe script was deleted rather than committed.

## One test that passed for the wrong reason
The wire spec's "rejects a patient token" case initially passed because `AuthGuard.validatePatient` threw "Missing required patient identifiers" — the token lacked `clinic_id`, so the request never reached the resolver's clinic-user gate at all. Green, and proving nothing. Fixed by building a token the guard accepts so the refusal comes from the layer under test.

## Left open
- Both PRs (#592 → main, #593 → stage_test) are draft and unmerged; nothing is deployed.
- FE (VP-18051) deliberately not started — Leo's call. Leo has no push access to va-portal anyway.
- The Confluence page "Accession Claim Module" (2414215212) is stale for two behaviors that are already live: `isAccessionClaimable`'s `consultDate`, and `resetEventAccession` now admitting clinical-team users. Not edited — outward-facing, and not asked for.
- Three PM questions parked for the closing Jira comment: undated fallback copy, MM/DD/YYYY timezone, and whether the row label applies to the pre-search Recent Orders list.
