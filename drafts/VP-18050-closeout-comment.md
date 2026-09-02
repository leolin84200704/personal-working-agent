# Jira comment — VP-18050 (POSTED 2026-09-02 15:07 PT as comment 186523, per Leo)

Shipped and live on both environments.

**What was added** (LIS-transformer-v2, PR #592 → main / PR #593 → stage_test, merged 2026-08-31, deployed via push-to-deploy):

A new batched GraphQL query on the transv2 endpoint (`/v2/portal/trans-service/graphql`):

```graphql
query ($ids: [String!]!) {
  accessionClaimStatuses(accession_ids: $ids) {
    accession_id
    claimable
    currentEventId
    consultDate
  }
}
```

- One entry per distinct accession id, returned in request order, so the FE can zip it against the rendered list.
- `claimable: false` + `currentEventId` when the accession is already used for a consult; `consultDate` is the ISO start time of the booking that consumed it (FE formats).
- `consultDate` carries the same disclosure gate as the existing `isAccessionClaimable`: it is returned only when the caller is the claimant, the holding event's creator, or a participant. Otherwise the row is still marked not claimable but the date is omitted.
- Clinic-user token only; at most 20 ids per call (matches the modal's search result limit; the cap is a probing limit, not a performance one).
- No change to eligibility logic. No schema or migration change.

**Why not in the search response itself**: the Select Related Test search calls `/trans/findPatient`, which is served by LIS-transformer (v1) and has no access to the calendar claim data. The FE (VP-18051) should call `accessionClaimStatuses` once per rendered list (search results and the recent-orders list) and use it for both the row-level "Consult booked" label and the banner date.

**Open questions for PM**
1. When the viewer is not tied to the holding consult the date is withheld by design. Please confirm the undated fallback banner copy, or decide whether the gate should be relaxed (that accepts a cross-practice probing risk).
2. Timezone: `consultDate` is UTC. Should MM/DD/YYYY be rendered in the provider's local timezone or UTC? Evening consults differ by a day between the two.
3. Does the row-level "Consult booked" label also apply to the pre-search "Recent Orders" list?
4. The banner copy in PH-898 (08/31) says resets are done by clinicians in Unimod, not Support. VP-18051 should use that wording, not the older support@ draft.
