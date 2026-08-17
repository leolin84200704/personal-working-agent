---
name: project-result-push-has-no-idempotency-gate
description: "Replaying a report-finished event re-delivers the ORU to the EMR vendor, and the duplicate is invisible in result_transmission_records row counts"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f9d68d5-e638-4be2-8830-177d69f39811
  modified: 2026-07-31T01:48:57.750Z
---

emr-v2 result push has **no "already sent" guard**. `ensureResultTransmissionRecord`
(`src/modules/result/services/result-generation.service.ts`, the `findFirst` on
sample_id + integration_request_id + push_scope_key) **reuses** any record younger than 24h —
it resets `generation_status`/`encoding_status` and then runs the full generate → write file →
SFTP transmit path again. The old `emr_sample.result_sent` gate was removed in VP-17408.

**Why:** any action that replays a report-finished event re-delivers the result to the vendor —
Kafka offset rewind or cluster switch-back, manual BullMQ re-enqueue, rescan. Confirmed on prod
2026-07-31: a cloud→on-prem Kafka revert replayed 71 minutes of events and re-transmitted 18
records / 17 samples to MDHQ (Cerbo) clinics.

**How to apply:** before any manual result re-drive, query for an existing TRANSMITTED record on
that (sample_id, integration, push_scope_key) within 24h — if one exists you are creating a
duplicate delivery, not a rescue. And never conclude "no duplicates" from a row count: the replay
overwrites the existing row instead of inserting. Detect with `created_at < <event>` AND
`updated_at >= <event>`, or the pod log line `♻️ Reusing existing transmission record`.

Related: [[project-ghost-rescue-duplicate-order-guard]] is the same trap on the order side,
[[project-verify-sample-core-not-emr-mirror]] on trusting the right table.
