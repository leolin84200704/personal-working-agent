---
name: Single-ticket vs umbrella migration scope
description: prod-wide audit findings surfaced during a single integration ticket belong to umbrella migration scope, not the ticket
type: feedback
originSessionId: d33fc38d-58f1-40ea-a0ff-8747c6aa8470
---
When working a LIS integration ticket (e.g. VP-16617 "Elation Harris LIVE") and an audit reveals prod-wide drift (missing integrations, schema gaps, dead-vendor leftovers, etc.), those findings do NOT belong to the originating ticket. They belong to the umbrella EMR-Backend → lis-backend-emr-v2 migration scope.

**Why:** Leo explicitly rejected attaching a 6-question PM CSV to VP-16617 with "已經不是這個 ticket 的範疇了。這個 ticket 已經 done. 這個是 migration from EMR-BACKEND to lis-backend-emr-v2 的範圍." Single-ticket bloat dilutes completion criteria and loses the migration umbrella's tracking position.

**How to apply:**
- In-scope to the integration ticket: the named integration going LIVE + invariant alignment directly derived from it
- Out-of-scope (route to migration umbrella): prod-wide drift, schema fixes, dead-vendor sweeps, cross-customer cleanup
- Tracking artifact names should not embed the originating ticket ID once findings are recognized as migration-scope (e.g. rename `vp16617-pm-questions.csv` → `emr-backend-migration-followups.csv`)
- Never auto-post broad audit findings as comments on the single ticket that surfaced them — present to Leo as draft + ask whether to route to migration scope
