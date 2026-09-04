---
date: 2026-08-04
slug: onprem-decom-audit
related_tickets: [VP-17593, VP-17594, VP-17595]
distilled: true
---

# On-prem decommission audit -> 3 fixes same day, plus VEJO integration deletion

## Context
Infra Slack: unplug all deps on local DB/Kafka/Redis + CDC topics 153_* (from 60.2) TODAY. Leo
asked for an emr-v2 + calendar audit, then fixes. Also ad-hoc: delete VEJO/VEJOEcomm/VEJOProgram.

## What we explored
- Audit method that worked: repo grep is NOT enough — live ConfigMaps (kubectl) exposed the two
  worst findings: transv2 prod still on carlos brokers for real flows, and setting.service's
  Azure env (Azure_kafka_host_gen) NEVER provisioned -> those events were lost on BOTH legs long
  before the decom. Ground truth beats code reading.
- git grep gotcha (again): '\|' alternation silently matches nothing — use -e per pattern. A
  false-negative grep almost concluded "transformer has no kafka code".
- CDC 153_*: zero references in both repos. ClickHouse 62.85 usage (emr-v2 scheduled-reports +
  my triage tooling) flagged to data team, unresolved.
- transv2 st shares the PROD notification hub/topic — staging E2E sends real emails.
- emr-v2 injects env via envFrom (CM key deletion safe); transv2 injects per-key
  (configMapKeyRef) — deleting a referenced key breaks pod start. Checked BEFORE cleanup.

## Decisions
- Leo: only calendar is my scope in transformer — VP-17594 (setting module) handed off, PR #552
  closed by Leo ("不需要管"). Over-reach acknowledged.
- Leo: "都清掉就沒問題。不用回覆，直接done" — CM keys cleaned post-deploy, both tickets Done,
  no Slack reply to infra.
- VEJO deletion executed directly (explicit request): 41 rows / 7 tables, zero-activity-ever
  verified first, txn with count guards, full backup at
  ~/src/credential/vejo-deletion-backup-20260804.json (has SFTP creds — kept out of git).

## Files touched
transformer PR #551 (merged, prod live), emr-v2 PR #318 (merged, prod live, CMs cleaned),
PR #552 (closed, handoff), STMs VP-17593/94/95 + VEJO-DELETION-20260804.

## Open questions / followups
- staging DBs still on 192.168.60.11 (emr-v2 + transv2) — undecided decom blocker.
- transv2 remaining on-prem: carlos brokers still used by dual-publish local legs (fail-soft) +
  DATABASE_URL_LIS dead key + 60.6 RPCs + 192.168.10.153 report URLs.
- ClickHouse 62.85 / CDC feed ownership unconfirmed.

## User feedback this session
- Scope discipline: fix only what's yours; hand off the rest even when the fix is easy.
- "有實際測過嗎" — claims need live-config/live-call evidence, not schema parity reasoning;
  the pod-env preflight (SASL connect + topic metadata, no message) is a good reusable pattern.
