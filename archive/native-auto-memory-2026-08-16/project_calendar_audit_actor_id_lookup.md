---
name: project_calendar_audit_actor_id_lookup
description: "Calendar accession audit `actor` strings are lis_core_v7 user_id (not internal_user_id/customer_id/patient_id); resolve via ClickHouse 192.168.62.85 lis_core_v7_replica.user"
metadata: 
  node_type: memory
  type: project
  originSessionId: ed161264-db4e-49f5-b29b-86f9ac10aff8
  modified: 2026-07-31T20:58:53.239Z
---

`v2_event_accession_audit_log.actor` / `v2_event_accession_claim.claimed_by` in calendar_prod are `'user:' + getUserId(jwt)` (LIS-transformer-v2 `auth.guard.ts` getUserId): clinic-user token → `user_id`/`userId`, patient token → `patient_id`.

Those numbers are **`lis_core_v7.user.user_id`** — NOT `internal_user_id` (the `internal_user` table has none of them), NOT `customer_id`, NOT `calendar_owner_id` (0 of 1147 claimed rows had actor == creator calendar's owner).

Resolve names:
```bash
CH="http://192.168.62.85:8123/?user=portalclick&password=ebRiCiTypIRa"
curl -sS "$CH" -d "SELECT user_id, username, email_user_id FROM lis_core_v7_replica.user WHERE user_id IN (...) FORMAT TSVWithNames"
# user_id -> person: join lis_core_v7_replica.customer ON customer.user_id = user.user_id
```
Use `lis_core_v7_replica.*`, not `lis_core_v7.*` — the non-replica ClickHouse snapshot stops at 2024-10, so newer accounts silently return zero rows.

**Trap:** the id namespaces collide across people. `user_id=173014` is David Thayer (customer 47292), while `patient_id=173014` is a different person entirely (PAUL POPKIN). The audit row does not record which payload type produced it, so establish the code path (clinic-user vs patient mutation) before naming anyone.

Found while triaging VP-17577 (duplicate consult bookings). Related: [[project_verify_sample_core_not_emr_mirror]], [[reference_transv2_calendar_doc]].
