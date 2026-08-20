# Consult recipient check (VP-17825)

Daily 06:45 launchd job. Flags clinical consults starting in the next 48h that the
reminder dispatcher will skip because no attendee has a `calendar_owner_email`.

## Why this exists

VP-17825: `dispatchEventReminder` filters out participants with no email and, before
the fix, returned silently when none remained — no log, no audit row, no metric. The
loss is invisible by construction: you cannot notice a missing row in an audit table.
Detection depended on a provider missing a Zoom call and mentioning it. That took six
months and 6,402 affected calendars to happen once.

48h is the earliest reminder's lead time, so a hit here is still fixable before the
provider is affected.

## Signal vs noise

The clinical team blocks its own calendar for OOO and admin notes ("OOO",
"Block - Dental", "awaiting updated times"). Those events carry a clinicadmin
participant only — the dispatcher correctly sends nothing and there is nobody to
alert about. They are counted and skipped, not reported. The alert fires only when
a real attendee exists and would still receive nothing.

## Files

- `check_consult_recipients.js` — read-only check; exit 1 on any hit **or** on its own
  failure (an unverifiable run must not look clean).
- `run_check.sh` — wrapper, macOS notification on non-zero.
- `com.lis.consult-recipient.plist` — launchd unit (06:45 daily).
- `consult_recipient_YYYY-MM-DD.md` — per-run report.

## Install

```bash
cp com.lis.consult-recipient.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lis.consult-recipient.plist
```

Reads `calendar_prod` through the `LIS-transformer-v2` checkout's `.env`
(`TRANSV2_DIR` to override). No credentials live in this repo.
