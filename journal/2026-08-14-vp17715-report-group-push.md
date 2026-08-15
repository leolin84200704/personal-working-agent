---
date: 2026-08-14
slug: vp17715-report-group-push
related: [VP-17715, VP-17723, VP-17344, VP-17493, VP-17441]
distilled: true
---

# 2026-08-14 — VP-17715 PER_REPORT_GROUP: from customer escalation to live in one day

Related: VP-17715, VP-17344, VP-17493, VP-17441

## Arc
Terry relayed Dr Prusmack's (cust 4953) exasperated spec: "a report should come through ONLY TWICE — once when everything except Gut Zoomer is resulted, once when GZ results IF it results." This session went escalation-triage → trigger-semantics confirmation (yesterday) → requirement translation → design → Story → implementation → merge (Leo) → DDL → deploy-verify → prod E2E → customer flip → Done, same day.

## What was explored / decided
- **Whose mental model wins**: Leo asked whether she might actually want per-fluid (urine/saliva/stool) grouping. Evidence said no: her own list lumps urine panels (OAC/HM2/MY2/ET2) with blood into one delivery; real push timelines show blood and urine interleave within days while stool lags weeks; and her "I couldn't possibly be clearer" tone warned against re-interpreting. Design kept a forward path anyway (deferred column is the 2-group special case of N-group config).
- **Trigger choice**: report-readiness (`new_report_status_updated`) over test-approval events — the addon carries `total_reports_short_names` INCLUDING not-yet-generated reports (verified in ClickHouse against her real accession 2607166082, 10/11 with GUT5 pending), and report-ready inherently includes calculated analytes (kills the +12-missing-calc-scores class of complaint).
- **Phase 2 = zero new code**: the existing report_finished whole-order push is the second delivery; the main-push condition requires `remaining ≠ ∅` so they can never double-fire. Edge cases (GZ-first, GZ-only accession, no GZ ordered, unconfigured deferred) all collapse to the final push.
- Leo's calls: no re-confirm with the customer ("直接回覆說我們已經按照他的設定了"); merge immediately; DDL by agent; test after deploy.

## Traps hit (worth remembering)
- Worktree node_modules cloned from a stale branch checkout missed staging's newer deps → 5 phantom TS2307 errors; `npm install` fixed. Clone-then-install, always.
- `ehr_integrations.status` has NO 'PAUSED' value (PENDING/APPROVED/LIVE/REJECTED) — retire test integrations with `result_enabled=0`.
- Replaying to cloud Event Hub from the prod pod works with the pod's own identity: kafkajs + SASL $ConnectionString + Key Vault secret `kafka-sas-connection-string` via DefaultAzureCredential.
- ClickHouse replica `lis_core_v7_replica.test_results` is an EMPTY shell table — don't plan verifications around it.
- E2E-on-same-customer safety: a test integration for the REAL customer is safe when eligibility filters by push level — the replay can only match the test row, never the customer's production destination.

## User's actual words that shaped scope
- "我覺得這才是sample_type 正確的方式" — push granularity should be the customer-visible unit (reports), not the lab-internal one (specimen containers).
- "不用再確認一遍，直接回覆說我們已經按照他的設定了" — bias to act; the confirm-question was drafted but consciously dropped.
