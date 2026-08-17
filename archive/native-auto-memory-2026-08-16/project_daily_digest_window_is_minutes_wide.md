---
name: project_daily_digest_window_is_minutes_wide
description: "The daily-digest launchd job fires at 00:00 PDT, so its \"today\" window is only ~2-5 minutes and every digest reads 0/0/0 unless it backfills the previous day"
metadata: 
  node_type: memory
  type: project
  originSessionId: 504f8dcd-e280-4af7-a0b0-cd3657b23ebd
  modified: 2026-08-13T07:06:53.162Z
---

The Vibrant America daily-digest job runs at **00:00 America/Los_Angeles**. Its spec says to query "00:00 local today → now", so the actual window is only the ~2–5 minutes since midnight. Result: the in-window numbers are always `0 commits, 0 repos, 0 tickets`, which reads as "the team shipped nothing" when it means "the window was 4 minutes."

Confirmed on three consecutive nights: 2026-08-11 covered the first 2.5 min, 08-12 the first 5 min, 08-13 the first 4 min.

**How to apply:** each digest must (a) state plainly that 0/0/0 is a scheduling artifact, not an absence of work, and (b) add an explicitly-labelled 補記 section covering the *previous* full local day (`since=<prev>T07:00:00Z` → `until=<today>T07:00:00Z` for PDT), whose activity no earlier digest captured. Keep backfill numbers out of the headline summary so the two are never conflated.

**Why:** without the backfill, each day's real output is silently lost — 08-12 alone was 70 commits across 10 repos and 33 human-touched tickets, none of which any digest had recorded.

The real fix is moving the launchd schedule later (e.g. 23:30 local, or 06:00 covering the prior day); the backfill is a workaround, not a solution. Flag it to Leo rather than treating the nightly 0/0/0 as normal. Related: [[project_automation_jobs_own_logs]], [[feedback_never_conclude_breakage_from_a_quiet_window]].
