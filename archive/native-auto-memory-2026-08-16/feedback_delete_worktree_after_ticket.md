---
name: delete-worktree-after-ticket
description: "After a ticket's coding is pushed (PR up), remove the git worktree you created for it — don't leave worktrees lying around"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1fbf0ab5-509e-4a5d-9189-cb6953f4c5cc
---

Leo (2026-07-16, VP-17441): 「你的 worktree 在 ticket 做完後要刪掉」.

**Why:** Per-ticket worktrees under `lis-backend-emr-v2/.claude/worktrees/` accumulate and clutter the repo; each also carries a node_modules symlink. Once the branch is pushed and the PR is open, the worktree's local state is disposable.

**How to apply:** When a ticket's code work is done and pushed: `git worktree remove <path> --force` (rm the node_modules symlink first). The branch stays on local + remote so the PR is unaffected; if review requests changes, re-create with `git worktree add <path> origin/feature/leo/<ticket>`. Removing a worktree does NOT delete the branch or the PR. Related: [[ghost-rescue-duplicate-order-guard]] is unrelated; git discipline lives in CLAUDE.md.
