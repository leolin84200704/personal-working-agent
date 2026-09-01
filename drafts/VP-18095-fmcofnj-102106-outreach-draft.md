# DRAFT — outreach for clinic 102106 (FMCOFNJ) half-configured Optimantra integration (not sent)

To: integration team / practice contact labs@rebootvb.com (via whoever owns the channel)
Context ticket: VP-18095 (backfill audit lead #2)

---

Subject: FMCOFNJ (practice 102106) — Optimantra result integration was never completed; results are not being delivered

Hi,

While auditing result-delivery configurations (VP-18055 follow-up) we found that practice **FMCOFNJ (ID 102106)** has an Optimantra RESULT_ONLY integration request created on 2026-04-23 under the "Practice Admin" account (labs@rebootvb.com) that is **LIVE but was never completed**:

- The row has no receiving-facility value (MSH-6), no result path, and no EMR service code — it cannot deliver anywhere.
- It is also scoped to the Practice Admin account, which never appears on orders, so even a completed row would not match the practice's actual providers (22066 Nicole Anderson, 34100 Kelly Blundy, 40130 Amanda George, 48365 Komal Yadav).
- Net effect: **104 finalized reports in the last 60 days alone were never sent to Optimantra**, silently.
- We found no Jira/onboarding record for this integration, and the practice has zero inbound EMR order traffic — so we have no evidence the Optimantra side was ever configured either.

Before we can fix this and back-deliver the reports, we need two confirmations:

1. **Does the practice want results delivered into Optimantra for all four providers?** (We would provision a clinic-level configuration so every provider at 102106 delivers, matching how other practices are set up.)
2. **What receiving-facility identifier does their Optimantra account expect in MSH-6?** For other Optimantra practices this is the Vibrant practice ID (here: 102106), but it must match what Optimantra configured on their side — please confirm with the practice/Optimantra that their account is set up to receive Vibrant results and which identifier it is keyed to.

Once confirmed, the fix on our side is a single configuration row plus a re-push of the missed reports (we can scope the back-delivery window to whatever the practice wants).

Thanks!

---

## Internal notes (not part of the message)
- Half-configured row: ehr_integrations `cmobona3u00ht1007umovde34` (518714/102106, vendor 9 OPTIMANTRA, RESULT_ONLY, LIVE, msh06/result_path/legacy_emr_service all NULL, onprem, requested_by=100062, updated 2026-06-12 by 2477 — asking user 100062/2477 what happened may shortcut this).
- Optimantra mechanics: single shared drop folder `/Prod/Input/` for ALL practices; routing is entirely by MSH-6 → guessing it risks delivering PHI to the wrong practice inbox, which is why this is blocked on confirmation.
- Planned fix once confirmed: either flip the existing row to customer_id='-1' + fill msh06/`/Prod/Input/`/OPTIMANTRA/SFTP, or insert a fresh -1 catch-all and retire the broken row; then repush the missed samples (list reproducible via the VP-18055 signature scan bounded to clinic 102106).
- Pipeline note: existing row says onprem; Optimantra peers deliver from both; keep onprem to match unless told otherwise.
