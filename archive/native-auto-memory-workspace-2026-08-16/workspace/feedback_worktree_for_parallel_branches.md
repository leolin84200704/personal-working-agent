---
name: feedback_worktree_for_parallel_branches
description: Default to git worktree when handling multiple branches / parallel or stacked tickets; in-place checkout is fine only for a single linear ticket
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 25da76b7-c932-4728-aedf-05b96b1a128c
---

When work spans **multiple branches at once** — parallel tickets, or stacked/dependent branches that need decoupling — default to **git worktree** (separate working dirs, e.g. `git worktree add ../<dir> <branch>`, or spawn subagents with `isolation: worktree`). Don't do in-place `git checkout` juggling across branches.

**Why:** Leo's stated preference. In VP-17190 I kept VP-17065 (daily-report) and VP-17190 (timezone) stacked in one working copy and had to do reset + file-overlay surgery to decouple them, plus repeated branch switches churned the working tree (prisma2 generated client drift). Separate worktrees would have let both branches be checked out simultaneously, cleanly, with no switching.

**How to apply:** for a single linear ticket, in-place checkout is still fine (worktree setup isn't worth it). The moment a second branch enters the picture (parallel ticket, or a base/dependent branch), create a worktree per branch. **Repo caveat (LIS-transformer-v2 and similar):** each worktree is its own working dir → run `npx prisma generate` (both schemas) per worktree, and it may need its own `node_modules` (worktrees share `.git` but not `node_modules`). Clean up with `git worktree remove` when done. Related: [[feedback_start_dev_iron_rule]].
