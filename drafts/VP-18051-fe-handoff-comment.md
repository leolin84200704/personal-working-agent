# Draft Jira comment — VP-18051 (English, NOT posted; FE handoff to Zhiheng Wu)

BE side (VP-18050) is done and live on prod and staging.

Endpoint: transv2 GraphQL `/v2/portal/trans-service/graphql` (same client va-portal already uses for `isAccessionClaimable` in `SearchOrders.vue handleClickOrder`).

```graphql
query ($ids: [String!]!) {
  accessionClaimStatuses(accession_ids: $ids) {
    accession_id      # echoes the input, request order preserved
    claimable         # false → show grey non-clickable "Consult booked" in the New Report column
    currentEventId    # holding consult event id (null when claimable)
    consultDate       # ISO UTC; null when claimable OR when the viewer is not tied to that consult
  }
}
```

Suggested usage:
- Call once per rendered list (after `/trans/findPatient` returns, and for the recent-orders list), passing the visible accession ids. Max 20 ids per call; the search result limit is already 20.
- Row label: `claimable === false` → "Consult booked" (grey, non-clickable).
- Banner on click: if `consultDate` is present → `Consult already booked on {MM/DD/YYYY}. Ask your Vibrant clinician to reset it before booking again.` If `consultDate` is null (viewer not tied to the consult) → undated fallback copy, pending PM confirmation on VP-18050.
- Do not point the copy at support@vibrant-america.com; PH-898 (08/31) decided resets are performed by clinicians in Unimod.
- Timezone for the MM/DD/YYYY formatting is an open PM question on VP-18050.
