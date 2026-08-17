---
name: project-hl7-triage-db-port-blocked
description: "Daily HL7 triage job outbound port 3306 blocked in this execution environment — recurring since 2026-07-05 (confirmed again 2026-07-06)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 29343104-4191-4ed2-88ff-4093342a1d8b
---

Since 2026-07-05, the `hl7_file_input` daily triage job (writes to `DailyJob/hl7_fail/triage_{date}.md` — see prompt at `DailyJob/hl7_fail/triage_prompt.md`) has been unable to connect to prod MySQL `lisportalprod2.mysql.database.azure.com:3306`. Diagnosed with `nc -zv`: outbound TCP 3306 timed out to *any* host tested (including `1.1.1.1:3306`), while port 443 worked fine everywhere. Re-confirmed identically on 2026-07-06 — this is now a 2-day-consecutive, persistent block in this execution environment, not a one-off blip.

**Why:** Past successful runs (e.g. `triage_2026-07-02.md`) did complete DB queries and even prod payment/order recovery calls, so connectivity has worked before from whatever environment ran those — this looks like a difference between execution environments/sandboxes, not a permanent DB-side change. Two consecutive failing days raises the likelihood the daily job's execution environment itself changed (vs. a transient network blip).

Related but distinct symptom (2026-07-06 dream run): `scripts/reconcile-jira.py` failed twice with HTTPS *read* timeouts (connection established, response never arrived) to the Jira server — not the 3306 connect-block above, since 443 generally works. The 2026-07-05 reconcile run from a normal session applied fine. So dream/background runs may sit behind a more restricted or degraded network path than interactive sessions.

**How to apply:** Before trusting a "0 failed records" or empty result from this job, verify the DB connection actually succeeded (check for `[DB ERROR]` in script output) rather than trusting an empty row count — the existing `triage_runner_*.py` script's `run_query()` returns `[]` on both connection failure and genuine empty results, so a bare empty list is not proof of "no failures". If port 3306 is blocked again on the next run (2026-07-07+), treat it as confirmed-broken infra rather than re-diagnosing from scratch — escalate directly to Leo asking which environment/host prior successful runs (through 2026-07-02) used (VPN? specific runner machine?), since repeated silent diagnosis without a fix wastes a run each day.
