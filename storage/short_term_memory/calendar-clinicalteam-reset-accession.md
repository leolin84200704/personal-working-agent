---
id: calendar-clinicalteam-reset-accession
type: stm
category: technical
status: active
score: 0.0287
base_weight: 0.9
created: 2026-06-18
updated: 2026-06-18
links: []
tags:
- calendar
- accession
- rbac
- clinicalteam
summary: 讓 clinicalteam 可 reset event accession (LIS-transformer-v2 calendar)：guard
  豁免 + resolver 允許名單
---





















# calendar clinicalteam reset accession - Work Loop Record

> Created: 2026-06-18 UTC
> Status: done (PR #496 → stage_test, awaiting Leo merge)

---

## Ticket Analysis
- Leo 要求: `resetEventAccession` (LIS-transformer-v2 `src/calendar/models/accession-claim/`) 允許 clinicalteam。判斷 = `internal_user_role==='clinicalteam'` 或 `role==='clinicalteam'` 其中一個。clinicalteam **新增**到允許名單（admin/clinicadmin 保留）。
- 兩處 gate:
  1. guard `auth.guard.ts:485 validateClinicUser` 要求 user_id+clinic_id，clinicalteam token clinic_id=null → 丟 `Missing required clinic user identifiers` (在進 resolver 前)。
  2. resolver `accession-claim.resolver.ts:59` 要 `isClinicUserPayload && isAdminUser`；isAdminUser 只看 user_roles[]（clinicalteam 的空）。

## Decisions Made
- Leo 定: **guard 層豁免 clinicalteam（全 calendar 模組認證放寬）**；各路由自身授權仍生效。範圍只動 resetEventAccession 的授權（不動 claim/isClaimable）。

## Code Changes

### [2026-06-18] branch feature/leo/calendar-clinicalteam-reset-accession (從 origin/main)
- `auth.guard.ts`: 新增 export `isClinicalTeamUser(user)`（`internal_user_role` 或 `role` === 'clinicalteam'）；`validateClinicUser` 改 `if ((!hasUserId||!hasClinicId) && !isClinicalTeamUser(payload)) throw` → clinicalteam 免 clinic-identifier。
- `accession-claim.resolver.ts`: import isClinicalTeamUser；`resetEventAccession` 條件改 `!isClinicUserPayload(user) || (!isAdminUser(user) && !isClinicalTeamUser(user))`；error/description 文字加 clinical team。
- 共 +18/-4，2 檔；新增 `accession-claim.resolver.spec.ts`。

## Test Results

### [2026-06-18]
- `npm run build` 乾淨；無 CJK。
- 新增 resolver authz + isClinicalTeamUser 測試 **8/8 過**（clinicalteam via role / via internal_user_role+null clinic_id 皆允許；admin 仍允許；provider/patient 拒絕）。
- 既有 `auth.guard.spec.ts` + `accession-claim.service.spec.ts` **16/16 過**（無 regression）。
- 尚未 live e2e（待部署後比照 VP-17077 用真實 token 打 GraphQL 驗）。
## User Feedback
## Failures
## Retrospective
## Lessons Learned
