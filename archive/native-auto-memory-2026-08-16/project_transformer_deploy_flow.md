---
name: work-repos-staging-before-main
description: "All LIS WORK repos deploy staging-branch → main; fix PRs target the staging branch, never main directly. Only Leo's personal repos may go straight to main."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 693a8c46-ab8d-495d-a0bc-7a4502e35e85
---

**Work repos: always land on the staging branch first, then promote to main. Never open a fix PR directly against `main`.**

- The staging branch name is repo-specific: **LIS-transformer / LIS-transformer-v2 → `stage_test`**; **lis-backend-emr-v2 → `staging`**. When unsure, check the repo's branches / recent merged PRs for the staging branch, don't assume.
- Flow: feature/bugfix (vp) branch → staging branch → main. main is reached only by the later staging→main promotion (release step), not a direct feature→main PR.
- Branch the fix OFF the staging branch so its diff is clean against staging (and overwrites any earlier wrong fix already merged there).
- Migrations still apply to the prod DB first (Gate 3).

**Exception — Leo's PERSONAL repos may commit/push `main` directly:** `vibrant-america-working-agent` and `project-agent-factory` (still no force-push / reset --hard; automation-behavior changes like scripts/skills/launchd still go via PR per CLAUDE.md).

**Why:** 2026-07-16 Leo: "工作上一律都是先 staging 再 main, 我自己的私人 repo 可以直接 main." I'd opened VP-17422 #538 base=main (wrong) → re-did as #539 base=stage_test. [[always-share-pr-link]]
