---
name: feedback-no-direct-push-to-staging
description: Never push directly to staging; always open a PR for approval/merge
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd572592-84d4-40cc-b380-44631eaf282a
---

Never push directly to the staging branch (e.g. `stage_test`). Always **open a pull request targeting the staging branch** and let Leo find someone to approve/merge. This holds even when a repo's staging branch is not technically protected (e.g. LIS-setting-consumer's `stage_test` accepted a direct push, but it still should have been a PR).

**Why:** Staging deploys are gated by review; direct pushes bypass approval. Some repos protect `stage_test` (e.g. LIS-transformer rejected direct push), others don't — but the rule is the same regardless.

**How to apply:** Commit on `feature/leo/{ticket}`, push the feature branch, then `gh pr create --base stage_test --head feature/leo/{ticket}`. Do not merge it yourself. Supersedes the earlier reading where direct push to stage_test seemed allowed. Related: [[feedback_push_triggers_deploy]] [[feedback_no_chinese_in_code]]
