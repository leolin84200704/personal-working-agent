# Native harness auto-memory store — archived 2026-08-16

Verbatim copy of `~/.claude/projects/-Users-hung-l-src-vibrant-america-working-agent/memory/`
as it stood when the harness's per-cwd auto memory was turned off for this instance
(`autoMemoryEnabled: false`, framework position in factory `framework/RETRIEVAL.md`
§ Native harness auto memory).

**Nothing here is live.** The content was distilled into the instance memory first —
`long-term-memory/patterns.md`, `long-term-memory/emr-integration.md`, and the new
`long-term-memory/leo-working-rules.md`. Entries already carried by factory
`ENGINEERING-LESSONS.md` or by instance LTM were deliberately **not** copied forward;
duplicating them is the failure mode that retired this store.

The per-entry keep/drop decisions, with the reason for each, are in
`journal/2026-08-16-native-auto-memory-retirement.md`. Read that before concluding
anything here was lost.

These files use the harness's frontmatter schema (`name:` / `description:` / `metadata:`),
not the instance schema, and they sit in a subdirectory so `memory_scoring.py`
(which globs `archive/*.md`, non-recursively) neither scores nor indexes them.
