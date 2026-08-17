---
date: 2026-07-15
slug: vp17421-stale-reminders
related:
- VP-17421
- VP-16921
- VP-16499
distilled: true
---

# VP-17421 — reminders for a March-2025 appointment

P1: client got 24h/48h/15m clinical-consult reminders for a March-2025 event.

## What it was
Bull reminder queues (reminder_24h/48h/15m) hold delayed jobs. `sendReminderEmail`
(the Bull PROCESSOR path) only checked the event still exists (deleted=0), NOT that the
appointment is still upcoming. When the Bull redis reconnected/flushed ~2026-07-15 18:01 UTC,
overdue delayed jobs replayed → 338 spurious reminders to 149 customers. Fix = future-date
guard in the processor (PR #562, LIS-transformer). Enqueue path already guarded delay<0;
only the processor path was unguarded.

## Process lessons (the valuable part)
1. **Don't inherit a prior ticket's root cause.** This looked exactly like VP-16921 (rogue
   transv2/listest sending stale reminders) and I leaned that way early. It was a DIFFERENT
   mechanism (Bull overdue-job replay) in a DIFFERENT service. The VP-16921 STM was the right
   thing to READ, the wrong thing to CONCLUDE. Verify the mechanism every time.
2. **Restart-timing correlation misled me.** on-prem portal-calendar pods restarted at the
   burst time (17:59) so I fingered them — but their Bull can't even connect to redis
   (no REDIS_URL, localhost:6379 refused). Correlation ≠ cause; I only settled it by proving
   the actual Bull redis had the reminder queues (on-prem 192.168.60.9:4646, used by the
   lis-trans stprod pod) and portal-calendar's didn't.
3. **Postmark tag is the producer fingerprint.** Two reminder producers coexist: healthy
   transv2 dispatcher (Tag `calendar_prod`, "in in N hours", writes v2_reminder_audit_log,
   cron drip) vs the Bull one (Tag `CustomerEventReminder`, "in N Hours", no calendar_prod
   audit row). Comparing tag + subject wording + whether calendar_prod audit rows exist
   separated them instantly. Postmark token = noti/notification-center pod POSTMARK_KEY.
4. **"DB clean" cross-check:** calendar_prod v2_reminder_audit_log had only 1 row in the
   340-send burst window → the burst didn't go through the prod dispatcher. Audit-table
   vs Postmark-count mismatch is a fast producer discriminator.
5. Reminder code migrated Portal-Calendar (now ARCHIVED, unpushable) → LIS-transformer
   `src/calendar/email/`. calendarRedisOptions: stprod/mac→on-prem redis, else Azure.
   The reminder Bull queues run on-prem (stprod pod), so a stprod pod sends real prod
   emails — the VP-16921 design smell recurs, flagged to Leo.

## Containment outcome
Bull reminder backlog was ALREADY empty when checked (the burst drained the overdue jobs;
only harmless `:stalled-check` marker keys remained). Nothing to purge; #562 prevents
recurrence once deployed.

## Access note
access-and-secrets.md is still gone from the repo memory; needed calendar_prod (transv2
.env, same ehr-admin DB, schema via search_path; strip ?schema= for libpq) + on-prem SSH
(leo@192.168.60.5) + Postmark token (noti pod). Worth restoring that memory file.
