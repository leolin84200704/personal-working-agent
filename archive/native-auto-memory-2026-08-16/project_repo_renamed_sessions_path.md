---
name: repo-renamed-sessions-path
description: "Repo dir renamed lis-code-agent → vibrant-america-working-agent on 2026-07-06; Claude Code sessions are keyed by cwd path, old transcripts live under the old projects dir"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5cecab14-fbd1-4b27-965f-900915a16605
---

On 2026-07-06 the local repo directory was renamed from `/Users/hung.l/src/lis-code-agent` to `/Users/hung.l/src/vibrant-america-working-agent` (GitHub name also changed from personal-working-agent). Claude Code stores session transcripts per working-directory path under `~/.claude/projects/<escaped-path>/`, so after the rename `claude --resume` showed no prior sessions ("上個 session 東西不見了").

**Why:** transcripts are path-keyed; a directory rename orphans them in the old folder — nothing is actually lost.

**How to apply:** the 154 pre-rename sessions were rsync-copied (not moved) into `~/.claude/projects/-Users-hung-l-src-vibrant-america-working-agent/` on 2026-07-06. The old folder `~/.claude/projects/-Users-hung-l-src-lis-code-agent/` was left intact because background jobs may still append there; if a very recent pre-rename session seems stale, check the old folder for a newer copy. If the directory is ever renamed again, copy `*.jsonl` + session subdirs to the new escaped-path folder and diff the `memory/` dirs before merging.
