---
name: project_factory_path_is_under_src
description: "Two clones of the factory repo exist: the live ~/src/project-agent-factory, and a dead ~/agent-core that ~/.claude/CLAUDE.md still symlinks to"
metadata:
  node_type: memory
  type: project
  originSessionId: ac002654-b331-4525-a395-03cac0738cc0
  modified: 2026-08-16T23:29:23.110Z
---

The portable framework repo is at **`~/src/project-agent-factory`** (remote
`project-agent-factory.git`). It is the live clone.

**Two clones exist.** `~/agent-core` is a leftover from before the July 2026 repo
rename (`agent-core` -> `project-agent-factory`). Its remote still points at the
old `agent-core.git` URL, and it was **93 commits behind on 2026-08-16**.
`~/.claude/CLAUDE.md` symlinks to `~/agent-core/AGENTS.md`, so every session on
this machine loads a **stale user-level context** — missing core principle 0
("Sync With the World First"), the wave-doc rule, and any sync directive addressed
to this instance. The file is not missing and was not renamed; it is a live file
in a dead clone, which is why nothing errors. Repointing the symlink was raised
with Leo on 2026-08-16 and awaits his decision (it affects every agent on the
machine).

Docs used to say `~/project-agent-factory` (no `/src/`), which does not exist here.
dream.md's lesson routing is guarded by "if the path does not exist, skip", so
that silently killed universal-lesson routing on the nights of 2026-07-09, 07-22,
07-23 and 07-27. Fixed in project-agent-factory PR #34 and
vibrant-america-working-agent PR #24 (open as of 2026-08-16) — if either was
rejected, the old path is back and the skip returns.

Related gotcha: the factory is often left checked out on an **unmerged
`lesson/...` or `fix/...` branch** awaiting Leo's PR review, not on `main`. So
`ENGINEERING-LESSONS.md` may contain lessons `main` does not, and a plain
`git checkout main` makes them appear deleted when nothing was lost. Local `main`
also goes stale independently of `origin/main` — check both before judging.

See also [[feedback_distill_to_factory_habit]], [[feedback_always_share_pr_link]].
