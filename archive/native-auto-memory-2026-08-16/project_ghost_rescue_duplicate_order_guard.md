---
name: ghost-rescue-duplicate-order-guard
description: "Ghost-rescue re-upload can create a DUPLICATE order if the original stranded hl7_file_input row later reprocesses — before re-uploading, neutralize the original row and re-verify against lis_core_v7 after"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1fbf0ab5-509e-4a5d-9189-cb6953f4c5cc
---

2026-07-16 (VP-17312, MDHQ order_354 / patient CARMEN ALLISON 3256645): rescuing ghost-stranded row 6614 by re-uploading the file under a new name created order 11445283 / sample 2597033. But the ORIGINAL stranded row 6614 later (2026-07-16 11:04 UTC) reprocessed on its own and created a SECOND order 11445319 / sample 2597069 -> duplicate order, double charge risk ($870 customerPay). Order team had to CANCEL 2597033/11445283 and keep the original 2597069/11445319.

**Why:** The ghost-rescue playbook (re-upload archived original under a new filename) assumes the stranded row is permanently dead. It is not guaranteed — the original file can reappear on the vendor SFTP, or the stranded row can be retried/reprocessed, so BOTH paths turn into real orders. Leo: 「未來要避免這種重複下單的情況」.

**How to apply — before any ghost-rescue re-upload:**
1. Neutralize the original stranded row so it cannot later resolve into its own order: e.g. mark it terminal (parse_finished=1 with a RESCUE-SUPERSEDED error_detail) bound to its explicit id, BEFORE re-uploading. If the original file might still be fetched, coordinate to remove it from the vendor SFTP too.
2. Prefer letting the ORIGINAL resolve when possible; only re-upload if the original truly cannot (no archive, file deleted). If you must re-upload, pick ONE canonical path.
3. AFTER rescue, in the next watch ticks re-verify against ground truth `lis_core_v7.sample` + `order_info` (NOT emr_sample — see [[verify-sample-core-not-emr-mirror]]) that exactly ONE active order exists for that patient; if two, flag a duplicate to order team immediately with both order_ids.
4. Duplicate resolution (void/cancel) is order team's call, not the agent's. Root cause of WHY a /tmp-stranded row (localDir=/tmp, old pod name) reprocessed into a real order at 11:04 is still open — worth chasing. Related: [[hl7-triage-db-port-blocked]].
