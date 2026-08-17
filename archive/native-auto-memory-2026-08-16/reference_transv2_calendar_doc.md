---
name: transv2-calendar-reference-doc
description: "Full AI-reference doc for LIS-transformer-v2 calendar module (features, DB tables, Kafka/cron/Redis, auth, usage stats) — read it instead of re-exploring the code"
metadata: 
  node_type: memory
  type: reference
  originSessionId: de0da003-846b-477c-96e2-5786b0755677
  modified: 2026-07-28T22:45:59.245Z
---

`docs/reference/trans-v2-calendar.md` (in vibrant-america-working-agent repo) is a comprehensive reference for the trans-v2 calendar module, written 2026-07-28: 17 sub-modules, 7 core features with file:line anchors, calendar_prod table catalog + prod row counts, GraphQL/REST surface, auth roles, Kafka topics (producer-only; no BullMQ in v2 — Bull lives in legacy LIS-transformer), 4 crons, gotchas (150105 magic practice, is_canceled-only status, dead tables). Answer calendar questions from this doc first; re-verify only line numbers and "current state" claims.
