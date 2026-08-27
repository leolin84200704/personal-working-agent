---
date: 2026-08-26
slug: lis-7716-report-option
tickets: [LIS-7716]
distilled: true
---
# LIS-7716 — report style self-service (backend) + walkthrough doc refresh

## What happened
- Ticket from Tianhao (Zendesk 746900 / Maristany / Cerbo): report_option create-only, silently reset to CLASSIC on auto-integrate re-provision. Explored emr-v2 + portal side with two parallel Explore agents.
- Key discovery beyond the ticket: re-provision creates a brand-new ehr_integrations row (no upsert/unique constraint); push resolves duplicate LIVE rows via weak findFirst ordering — the real reset mechanism. Posted as Jira comment 185604 (Leo approved) proposing a dedupe follow-up.
- Debate (pro/con agents) changed the design: con showed a transformer-v2 gateway gate is bypassable by direct emr-v2 calls (any same-practice staff JWT), and that the authz property is untestable across repos. Moved enforcement to the resource owner: emr-v2 reads the signed `user_roles` claim (exact-match CLINIC/CLINICADMIN/CLINIC_ADMIN_ADDON) + clinic ownership, explicitly ignoring skipDataAccess (VP-16980). Negative tests became single-repo.
- Explored options were 4-repo (portal→transformer-v2→emr-v2) vs direct; Leo approved direct + two slices, then mid-flight cut slice 2: "不要改前端...我讓前端自己寫" — frontend patches backed up to session scratchpad (lis7716-va-portal-frontend.patch / lis7716-ehr-frontend.patch), worktrees/branches deleted, nothing pushed.
- Shipped (lis-backend-emr-v2, feature/leo/LIS-7716, pushed): PATCH :id/report-option (LIVE-only, audit note + last_modified_by, sibling-LIVE surfacing), create() carry-over (same-vendor LIVE preferred, stubs excluded), update() 400s on reportOption (was silent no-op, same class as VP-17408), JwtPayload user_roles claim, response DTO field. 18 new tests, integration-management suite 411/411, nest build pass.
- Live verify before coding (read-only prod, password needs URL-decode): report_option is enum('CLASSIC','PERSONALIZED') default CLASSIC (980/136); notes + status_history tables exist → no migration needed.
- Confluence walkthrough (page 2032566286) rewritten to current code — scratchpad/lis-backend-emr-v2-walkthrough.md — including a dedicated API-contract section for the frontend team. MCP has no Confluence write scope; Leo pastes it.
- Factory lesson PR #71: update endpoints must reconcile accepted fields vs handler-consumed fields (PartialType accept-but-ignore trap; VP-17408 + LIS-7716 two cases).

## Ruled out / why
- Transformer-v2 relay (canonical PRACTICE_SETTING_WRITE + central AuditLogService): rejected — new upstream client for zero access today, back door stays open unless emr-v2 gates anyway, 4 repos.
- Substring 'clinic' role match (transformer fallback style): rejected for exact-match set — 'clinic_staff' must not qualify.
- Changing the no-prior-row default to PERSONALIZED: Leo kept CLASSIC (product decision deferred).

## User's words
- 「B 方案 OK，預設維持 CLASSIC，comment 起草吧」
- 「commit + push，comment 照草稿發，slice 2 開工, 完成後 {Confluence page} 要更新成最新版」
- 「不要改前端，只要改後端然後把doc 寫好我讓前端自己寫他的東西就好」
