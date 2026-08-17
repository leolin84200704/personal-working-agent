# Native auto-memory — the other six stores, archived 2026-08-16

Byte-identical copies of every remaining path-keyed auto-memory store on this machine,
taken when native auto memory was turned off everywhere. 68 files.

| dir | source store | files |
|---|---|---|
| `workspace/` | `~/.claude/projects/-Users-hung-l-src/memory/` | 54 |
| `EMR-Backend/` | `…-Users-hung-l-src-EMR-Backend/memory/` | 4 |
| `lis-code-agent-prerename/` | `…-Users-hung-l-src-lis-code-agent/memory/` | 3 |
| `project-agent-factory/` | `…-Users-hung-l-src-project-agent-factory/memory/` | 3 |
| `lis-backend-emr-v2/` | `…-Users-hung-l-src-lis-backend-emr-v2/memory/` | 2 |
| `LIS-transformer-v2/` | `…-Users-hung-l-src-LIS-transformer-v2/memory/` | 2 |

The repo-keyed store retired the day before is separate:
`archive/native-auto-memory-2026-08-16/` (37 files).

**Nothing here is live.** 15 entries were written forward into
`long-term-memory/leo-working-rules.md`, `patterns.md`, `emr-integration.md` and `repos.md`;
the rest were already carried by factory `ENGINEERING-LESSONS.md`, by instance LTM, or by an
STM. Every keep/drop decision and its reason is in
`journal/2026-08-16-remaining-memory-stores-migration.md` — read that before concluding
anything here was lost.

Why six stores existed at all: Claude Code partitions auto memory by **cwd**, so where a
session happened decided which store it wrote to. Sessions started from the workspace root
wrote to `workspace/`, sessions started inside a product repo wrote to that repo's store, and
a directory rename in July orphaned a whole store under the old path. Nothing errored; the
partitions were simply invisible from one another. Same shape as the session transcripts
orphaned by that rename.

Two caveats for anyone reading these files:

- `workspace/reference_azure_mysql.md` contains a plaintext production DB password. It is
  **not** a new exposure — the same credential is hardcoded in 8 already-committed files
  under `DailyJob/` — but that is a problem to fix, not a supply channel. The schema facts
  worth keeping were written into `emr-integration.md` without the password.
- `project-agent-factory/remote-agent-bridge-project.md` and
  `personal-project-not-vibrant-framework.md` describe a **different** project
  (`~/personal/remote-agent/`), not LIS work. They are kept here only for provenance; that
  instance owns the content.

These files use the harness frontmatter schema (`name:` / `description:` / `metadata:`) and
live in subdirectories, so `memory_scoring.py` — which globs `archive/*.md` non-recursively —
neither scores nor indexes them.
