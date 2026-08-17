---
name: project-bestdeal-silently-drops-addon-tests
description: "BestDeal accepts ordered test ids and returns fewer, reporting nothing — affects single-gene genetics add-ons; how to detect and audit it"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8d79ed9c-df6d-4ef0-bbce-d58e1e48249f
  modified: 2026-08-12T20:03:52.064Z
---

`POST https://api.vibrant-america.com/v1/bestdeal/GetBestDealSuggestion` (order team's service, no staging URL — both emr-v2 staging and prod call this one) drops some orderable items **silently**: absent from `left_over_test_id_list`, absent from `non_existing_test_ids`, `best_deal_price` `0.00`. Deterministic, not flaky. Confirmed 2026-08-12 (VP-17686).

A genuinely bogus id **is** correctly reported in `non_existing_test_ids` — so the contract exists and simply is not used for these. That contrast is the proof it is a defect, not "those ids aren't provisioned".

**Affected (sandbox sweep of all 64 catalog codes):** APOE_BLOOD, APOE_SALIVA, CELIAC_GENETICS, FACTOR_II_V_BLOOD, FACTOR_II_V_SALIVA, MTHFR_BLOOD, MTHFR_SALIVA — single-gene genetics add-ons (ids include 855, 861, 866). Outcome is **combination-dependent**: `["861"]` alone drops it, `["855","861"]` returns 861. The set also drifts as the catalog changes, so old evidence can stop reproducing.

**How the request is made** (identical in emr-v2 and legacy Java, so not an emr-v2 regression): body is only `{test_id_list, discount_panel_id_list}` — no customer/clinic/patient. Auth is a fixed shared system JWT (`ORDER_API_TOKEN`, customer 999997, exp 2044). BestDeal therefore cannot know who is ordering; whether its pricing is customer-scoped is an open question worth asking the order team.

**Coverage is knowable from the response**: each `suggest_bundle_list[]` entry lists `zoomers` / `supplements` = the test ids that bundle covers. Both null = pure bundle, contents undisclosed → cannot compute drops, do not claim any.

**Audit query**: `emr_sample.test_input` (requested) vs `best_deal_output_test` (leftovers) + `best_deal_output_bundle`. Prod scan found 61 samples with unexplained missing ids (hs-CRP 339, Ferritin 300, Insulin 336, SHBG 311, Testosterone 313 lead the list). Many "missing" rows are legitimate bundling — expand the bundle's `zoomers`/`supplements` before calling anything a loss.

emr-v2 side is handled: total loss → 422, partial loss → `[BESTDEAL_DROPPED_ITEMS]` log only (blocking partial orders was Leo's explicit call: keep placing them). Hand-off to the order team still pending as of 2026-08-12.

Related: [[feedback-never-500-for-caller-actionable-failures]], [[project-vatest-code-lookup-path]]
