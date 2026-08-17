---
name: project-vatest-code-lookup-path
description: "emr_code_not_found VATEST* codes need getLegacyPackagePriceMapping + isOrderable check, not bundle mapping — daily triage prompt's Step 3 instructions are wrong for non-VACP prefixes"
metadata: 
  node_type: memory
  type: project
  originSessionId: e6ff9ccd-a546-45f2-9ed3-84bc7bd3bff9
---

The daily `hl7_file_input` triage job's Step 3 instructions (`DailyJob/hl7_fail/triage_prompt.md`, also embedded in the launchd prompt) tell the agent to resolve every `emr_code_not_found` code via the bundle mapping API (`getLegacyBundleMapping`) and search for a `panelId`. That is only correct for `VACP{panelId}` codes.

**Actual lookup path per prefix** (confirmed 2026-07-10 by reading `lis-backend-emr-v2`'s `obr-parser.service.ts` / `order-mapping-cache.service.ts` and `EMR-Backend`'s `ParseHL7.java`):
- `VACP{panelId}` → `getLegacyBundleMapping` API, dict keyed by bundleId, match on `oldOrderTypeId`.
- `VATEST{orderTypeId}` (individual test) → `GET https://api.vibrant-wellness.com/v1/pricing/item/price/getLegacyPackagePriceMapping?currency=usd`, dict keyed by numeric id, match on `orderTypeId`; **requires `isOrderable === "true"`** — a code that exists but has `isOrderable: "false"` is treated as not-found and lands in `emr_code_not_found` exactly like a truly-missing code.
- `VAREQUISTION{groupId}` (panel/requisition) → same `getLegacyPackagePriceMapping` API, but matched via `emrCodeToPackagePriceMap` (lowercase EMR code key), also gated on `isOrderable`.

**Why this matters:** the 2026-05-22 (`VATEST79`) and 2026-07-09 (`VATEST2287,...`) triage reports both used the bundle-mapping API on VATEST codes, got no match, and wrote the diagnosis "not found in mapping." Re-checking 2026-07-10 with the correct API showed all 6 of the 07-09/07-10 codes DO exist (as individual vitamin serum tests) but have `isOrderable: "false"` and `priceVa: -1` (no VA price, only `priceVw`) — i.e. a pricing/catalog config gap (possibly VW-only tests not enabled for VA ordering), not a missing-mapping problem. The shallow diagnosis in past reports would have sent PM/Order team down the wrong path ("register this code") instead of the right one ("enable isOrderable + set priceVa, or confirm these should route through a panel instead").

**How to apply:** before diagnosing a Type A `emr_code_not_found` record, branch on the code's prefix (VACP vs VATEST vs VAREQUISTION vs other) and call the matching API — never assume bundle mapping covers all of them. If multiple comma-separated codes are in one `emr_code_not_found` field, split and check each independently since prefixes/APIs can differ per code (though in practice they've all matched so far). This also means the `triage_prompt.md` Step 3 instructions likely need a fix — flagged to Leo 2026-07-10, not yet applied (automation-behavior files need a PR per [[project_repo_renamed_sessions_path]]-adjacent rule, not a direct commit).
