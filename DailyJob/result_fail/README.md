# Result Delivery Failure Watch

Answers one question every morning: **is there a lab report a clinic should have received and did not?**

## Why it exists

The order side has had a daily triage since April. The result side had nothing. When result
generation or delivery fails, the BullMQ job retries 5 times with exponential backoff
(base 120s, so roughly a 30-minute window) and then `markPermanentFailure()` writes the
error onto `result_transmission_records`. Nothing reads it after that:

- `TIMEOUT_RETRY` (VP-17343) only fires from a request-level timeout, not from a schedule
- emr-v2's `@Cron` jobs cover order fetch, mapping cache and scheduled reports only
- no alert, no dashboard, no query

So a failure that outlives the retry window means the report is never delivered and nobody
finds out. VP-17631 made the OBR-grouping path fail loudly rather than silently mislabel
panels — which converts "wrong report delivered" into "no report delivered", an improvement
only if somebody is watching. This job is that somebody.

Proven on its first run (2026-08-06): it surfaced the **Cascades** SFTP destination as
broken since 2026-06-18 — five reports undelivered over seven weeks, previously unknown.

## What it reports

1. **Destinations whose last attempt failed** — all time, deliberately not windowed. A
   vendor that broke months ago must not age out of the report.
2. **Undelivered reports** — not `TRANSMITTED`, untouched for 2h+, and no later successful
   delivery of the same sample to the same destination.
3. **Auto-repush log** — only when `AUTO_REPUSH=1`.

### Two query decisions worth keeping

**Do not filter on `next_retry_at IS NULL`.** Nothing consumes that column, so a row with a
future `next_retry_at` is just as abandoned as one with `NULL` — and a failed manual retry
sets it, which would hide the row precisely when it most needs attention.

**Do not filter on a status pair.** Where it broke decides the pair:
`GENERATION_ERROR/TRANSMISSION_ERROR` when grouping or an upstream call failed,
`GENERATED/TRANSMISSION_ERROR` when only the upload failed, `PENDING`/`GENERATING` when the
job died mid-flight. All three mean the same thing to the clinic. Ask about the outcome.

## Auto-repush

Off by default. With `AUTO_REPUSH=1` the job re-drives a row only when all of these hold:

- the error class is one where a plain re-drive is the whole fix
  (`obr_grouping`, `upstream_grpc`, `sftp`, `pod_restart`) — anything else is reported for
  a human instead
- no later successful delivery exists for that sample and destination
- the integration is still `LIVE` with `result_enabled = 1`

Calls are paced ≥10s apart (bursts degrade the lis-core v1 gRPC service — VP-17493), capped
at `RESULT_FAIL_MAX_REPUSH` per run, and each one is verified against the live row afterwards.

## Running it

```bash
DailyJob/result_fail/run_result_fail.sh          # report only
AUTO_REPUSH=1 DailyJob/result_fail/run_result_fail.sh
```

Requires the VPN for the repush gRPC endpoint (`192.168.60.6:31317`); the wrapper refuses to
run at all when prod MySQL is unreachable rather than reporting an empty result set as "no
failures".

| env | default | meaning |
|---|---|---|
| `AUTO_REPUSH` | `0` | re-drive eligible rows |
| `RESULT_FAIL_LOOKBACK_DAYS` | `30` | window for the undelivered table |
| `RESULT_FAIL_QUIET_HOURS` | `2` | how long untouched before a row counts as abandoned |
| `RESULT_FAIL_MAX_REPUSH` | `10` | cap per run |
| `RESULT_REPUSH_GRPC` | `192.168.60.6:31317` | on-prem result-generation service |

## Scheduling

`com.lis.result-fail-watch.plist` runs it at 05:00, an hour after the HL7 order triage so the
two never contend for the VPN pre-flight. Not installed by this PR:

```bash
cp DailyJob/result_fail/com.lis.result-fail-watch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lis.result-fail-watch.plist
```
