# Weekly skill scan log (skillsmp / GitHub)

> Results of the twice-weekly skill scan (hook: `~/.claude/hooks/skillsmp-reminder.sh`).
> Scope filter: DB migration safety, test/build verification, code review, schema/query
> analysis, backend reliability/observability, repeated-rules-to-git-hooks.
> Hard-excluded: vibe-coder, frontend, content, autonomous-loop (ralph-wiggum class).
> One dated entry per scan, newest first. Watchlist at the top carries forward.

## Watchlist (carry-forward)

| Added | Tool | Why watching | Trigger to adopt |
|---|---|---|---|
| 2026-08-18 | [Hainrixz/claude-db](https://github.com/Hainrixz/claude-db) | Schema audit (23 modules, reproducible evidence, read-only default) + lock-aware migration generation (concurrent index builds, `NOT VALID`+`VALIDATE`, expand/contract). Substantive, not a prompt wrapper. Caveats: Postgres-idiom techniques (limited value for emr-v2's manual-DDL MySQL; relevant to transformer-v2 calendar Postgres); early-stage (5 commits / 18 stars). | Next large calendar (Postgres) schema change — run its audit as a pre-review pass and evaluate. |

## 2026-08-18 scan

- **claude-db** → watchlist (above).
- Reviewed and rejected:
  - [anthroos/claude-code-review-skill](https://github.com/anthroos/claude-code-review-skill) (38★, 280+ checks) — checklist-style review, overlaps built-in `/code-review` + cursor-bot on our PRs; categories skew frontend (accessibility/React).
  - [aidankinzett/claude-git-pr-skill](https://github.com/aidankinzett/claude-git-pr-skill) — agent posts PR reviews directly; opposite of our "agent drafts, Leo reviews" model.
  - [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) — observability of Claude Code agents themselves via hook events; conceptually interesting for the dream/triage fleet but requires running a server; ROI not there.
- Everything else: directories/listicles or "community-needed" placeholders.

## 2026-08-14 scan

- No adoptable findings. DB-migration and SQL-analysis entries in major lists were
  "community-needed" placeholders; concrete code-review/verification candidates were the
  long-known [obra/superpowers](https://github.com/obra/superpowers) set (systematic-debugging,
  verification-before-completion) — not new; one small-repo pr-review skill with no adoption
  signal.
