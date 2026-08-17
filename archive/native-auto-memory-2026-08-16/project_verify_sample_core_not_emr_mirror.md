---
name: verify-sample-core-not-emr-mirror
description: "To confirm whether a sample/order truly exists, query lis_core_v7.sample + order_info (ground truth), NOT the lis_emr.emr_sample mirror — the mirror can be missing even when the sample is real"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1fbf0ab5-509e-4a5d-9189-cb6953f4c5cc
---

2026-07-16 (VP-17312 ghost-strand 6614 duplicate check): I told Leo "no duplicate" after checking only `lis_emr.emr_sample` for sample_id 2597069 — it returned nothing, so I concluded the sample didn't exist. Leo said "2597069 我能查到欸". It WAS real: it lives in `lis_core_v7.sample` (id 2597069, order 11445319). `emr_sample` is only the EMR-integration mirror and 2597069 was never mirrored (only the resend 2597033 was, emr_sample id 6052). So MDHQ patient CARMEN ALLISON (3256645) really had a duplicate order.

**Why:** `emr_sample` (in the `lis_emr` schema) is a downstream mirror populated by the EMR result/integration path; a sample can exist in core but never reach the mirror (parse resolved but integration didn't run, or ran on a different row). Trusting the mirror for an existence check gives false negatives — exactly the "Memory/answer References the World, verify against ground truth" trap.

**How to apply:** For "does this sample/order exist / is it a duplicate" questions, query the CORE source of truth on the SAME server (`lisportalprod2`): `lis_core_v7.sample` (by sample_id) and `lis_core_v7.order_info` (isActive, order_canceled, order_status by order_id). Use `emr_sample` only for EMR-mirror/result-delivery questions, and treat a mirror miss as "not mirrored", never as "doesn't exist". Server has schemas: lis_emr (EMR integration) + lis_core_v7 (core LIS). Read account lis_core_emr can read both. See [[execute-dont-just-verify]].
