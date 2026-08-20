# Consult recipient check — 2026-08-20

Window: next 48h from 2026-08-20T22:16:56.157Z
Consults scheduled: 31 (internal clinical-team blocks skipped: 10)
**Unreachable: 2**

| event | start | reason | calendars |
|---|---|---|---|
| 12757 | 2026-08-21T16:00:00.000Z | no clinicadmin participant | 48043 (owner 30209) |
| 12535 | 2026-08-21T20:30:00.000Z | no attendee has calendar_owner_email | 36115 (owner 516026) |

Fix: populate `calendar_owner_email` from the owner's LIS notification contact (VP-17825).
