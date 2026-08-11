---
date: 2026-07-08
slug: vp17344-partial-push-levels
related_tickets: [VP-17344, VP-17312]
distilled: true
archived: '2026-08-09'
---

# VP-17344: configurable partial result push levels — investigation → design → ship in two sessions

## Context
Yekai Liu (results team) relayed via Leo: customers want per-test or per-sample-type result pushes instead of waiting for the whole order. Asked whether ClickHouse `general_sample_events` (192.168.62.85:8123, kafka db) could distinguish the three partial cases.

## What we explored
- Full event inventory of `%finish%` events + payload sampling in ClickHouse; producer semantics verified in LIS-backend-results-core `test-status.service.ts` (products_finished = just-approved batch completes a product; checkSampleTypeFinishStatus computed per-type completion but only emitted the TNP variant).
- Found the gap: no plain per-sample-type finish event. Reported it; Yekai then ADDED `sample_type_all_finish` (superset of `_with_tnp`, independent message so existing consumers unaffected) within a day — gap dissolved mid-ticket.
- `personalized_report_ready` is all-reports-done, NOT per-report → per-report trigger must be `new_report_status_updated` (fires on ready AND viewed; consumer diffs itself; producer sends sample_id=0 so barcode→sample via `getSampleIdByBarcode`).
- lis-result events carry customer_id NULL / clinic_id 0 → resolve via `getSampleRelevantInfo(sample_id)`.
- Debate risks that shaped the design: PDF download retry spiral if partial push runs with add_report>0 before report generation (~70s x5 BullMQ retries); `getLatestApprovedTime` returns '' pre-report; monitoring assumes one record per sample+integration.

## Decisions
- Leo: build both levels but ship 100% dormant ("全部先只有 final result ready 才 push，我會手動調架構，end user 感受不到差異"); PR target staging (his explicit override of the usual stage_test flow); agent runs the DDL.
- Design: `ehr_integrations.result_push_level` enum gate + `result_transmission_records.push_scope_key` scoping; 60s-cached opt-in gate before any per-event work; partial pushes force add_report='0'; final whole-order push retained (no-stall AC); REPORT scope never re-pushes, SAMPLE_TYPE re-pushes after 24h.

## Files touched
lis-backend-emr-v2 commit 1def093 (8 files, +590): schema + migration, kafka listener (+335), queue job data, processor, generation service input, listener spec (+3 tests). PR #240 → staging. DDL applied+verified prod & staging same day.

## Open questions / followups
- VIP practice identity + vendor expectations for partial HL7 files (OBR/OBX preliminary-vs-final semantics) — untested until enablement E2E on staging.
- Runbook §8 duplicate-check monitor will flag multi-record samples once a partial level is enabled — needs a `push_scope_key IS NULL` filter added when that day comes.

## User feedback this session
- Leo overrode the two open design questions by simplifying: functionality now, activation later, manually. No corrections to the technical approach.
