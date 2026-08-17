---
name: project_automation_jobs_own_logs
description: "The three nightly jobs (dream/HL7 triage/daily digest) each keep their own per-run log; launchd's stdout is permanently empty, so \"no output\" never proves a job didn't run"
metadata: 
  node_type: memory
  type: project
  originSessionId: b782722d-497b-4921-9e4b-492f1104090d
  modified: 2026-08-06T01:45:41.181Z
---

Three nightly launchd jobs: `com.vibrant-america-working-agent.dream` (6:30 PM),
`com.lis.hl7-triage` (4 AM), `com.lis.vibrant-daily-digest` (midnight). **Each script writes its
own per-run log; the launchd `StandardOutPath` files are often 0 bytes forever.**

- dream → `logs/launchd-stdout-YYYY-MM-DD.log` (in this repo)
- HL7 triage → `DailyJob/hl7_fail/run_YYYY-MM-DD.log` (report: `triage_YYYY-MM-DD.md`)
- daily digest → `~/.lis-daily-digest/main/logs/daily-digest/YYYY-MM-DD_HHMMSS.log`
  (a **separate worktree**, not this repo; its launchd log is 0 bytes dated 6/23 and always was)

**Why:** on 2026-08-05 three consecutive dream logs (08-01, 08-04, and my own first read) had
declared the digest "dead / still silent" purely because `long-term-memory/daily-digest/` newest
was 07-29. It was firing every single night and dying on `API Error: Connection closed
mid-response`. The 0-byte launchd log made "never ran" look *more* substantiated, not less.

**How to apply:** before claiming any scheduled job is broken, open the job's own log directory
above. Distinguish three states that all look identical from the output directory: didn't fire /
fired and failed / fired and succeeded but wrote elsewhere. Also: all three jobs share one
failure mode (platform API instability), so when one looks broken, check whether the others
failed the same night — a common cause beats three separate config theories.

Related: [[feedback_never_conclude_breakage_from_a_quiet_window]],
[[project_hl7_triage_db_port_blocked]]
