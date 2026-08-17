---
date: 2026-08-16
slug: remaining-memory-stores-migration
related: [native-auto-memory-retirement, RETRIEVAL.md, ENGINEERING-LESSONS.md]
distilled: false
---

# 2026-08-16 — The other six auto-memory stores: 68 entries, item-by-item

Second half of the auto-memory retirement. The first pass took the repo-keyed store (37
files) and reported it complete; finding a citation that "did not exist" showed it was not.
Seven stores existed. This is the record of the remaining 68 decisions.

## Why seven

Claude Code partitions auto memory by **cwd**. Where a session happened decided which store
it wrote to, and nothing surfaces the partition — a pointer written from one cwd simply reads
as missing from another. A July directory rename orphaned an entire store under the dead path
on top of that. Same shape as the orphaned session transcripts, and the same shape as the
factory-path bug: a cwd-derived assumption that fails silently instead of loudly.

## Routing rule (unchanged from the first pass)

1. Already in factory `ENGINEERING-LESSONS.md` → drop.
2. Already in instance LTM or an STM → drop.
3. LIS operational fact with no home → write into the routed LTM file.
4. Leo working rule with no home → `leo-working-rules.md`.

Coverage was checked with **non-inferable probe strings** — API operation names, gRPC method
names, DB column names, env var names — never the topic word. That discipline was promoted to
a factory lesson this same session, and it earned its place twice more below.

## Written forward — 15 of 68

**`leo-working-rules.md` (6)** — the four-part IRON analysis format (with its re-offence
record), the team API-doc format, pursue-cleaner-design *and its counterweight* (verify the
cleaner option before asserting it), the build-must-pass iron rule with the prisma
client/schema drift case, ticket-scope routing to the migration umbrella, and the skill
description-optimisation prompt.

**`emr-integration.md` (5)** — HL7 encoding is emr-v2's own responsibility so trace the chain
before any scope claim; field-by-field parity across *all branches* when porting from the
Java service; bundle `clinicId` null vs integer = customer vs clinic level; clinic_id
fallback must re-check expiry per level; what the `lis_core_emr` Azure account can read plus
the `patient_first_name` column-naming trap.

**`patterns.md` (3)** — emr-v2's two uncommitted `.git/hooks/` (invisible in the repo, lost
on re-clone, verified still live today) and the two user-level reminder hooks; the
daily-digest job's full operating envelope (launchd, detached-HEAD worktree, the sleep/keychain
failure modes, the `pmset` wake schedule, the token-rotation trap); and the PNS 2FA email
pipeline end to end, including the two-Postmark-server split that makes a message look missing.

**`repos.md` (1)** — the scheduled-reports JWT scope boundary. The payload itself is already
in the code, so what was worth keeping is the rule the code cannot state: this identity is for
this server-driven flow only, and end-user report downloads must use the caller's own JWT.

## Dropped — 53 of 68

**Already factory lessons (19).** Batch DB verify, Cleanup filter scope, Test before push,
Verified means live not mock, Verify peer-observed state, JOIN scope reverse audit, Schema
migration before deploy, Preserve evidence before restart, Owner-scoped not actor, Prefer
stable id, Migrate all readers no mirror, Sync sibling encodings, End-to-end equivalence,
Audit callers when adding fallback, No overgeneralize, Worktree for parallel branches,
Capability flag enables a pipeline, Check live state before migration, Config coupled with
code. This store is visibly the raw material the factory was built from.

**Already in AGENTS.md / CLAUDE.md / leo-working-rules (9).** Analysis-before-execution,
Jira comment drafting, Jira in English, no CJK in code, no direct push to staging,
push-triggers-deploy, consult-the-instance-first, the Atlassian notice filter, and the CORS
`access-control-allow-origin` rule (factory § 驗證紀律 line 80).

**Already in instance LTM or an STM (13).** EMR-Backend retired, SFTP singleton / POD_ROLE,
FHIR order API feasibility (`fhir-api.md` + VP-16934), VP-16945 provider timezone (STM),
VP-17065 daily report (STM), cloud migration endpoints, appserver04 SSH, coresamples v2 sample
id, order customer resolution (superseded by the skill), trans-v2 calendar service and prod
test send, the pre-rename store's two duplicates (older copies of entries already archived
yesterday), and over-engineering (AGENTS.md principle 4).

**Not this instance's content (2).** `remote-agent-bridge-project` and
`personal-project-not-vibrant-framework` belong to a different project at
`~/personal/remote-agent/`. Archived for provenance only; that instance owns them. Its own two
stores are empty, and its settings still have auto memory unset — flagged, not touched.

**Historical, superseded (10).** The 2026-07-04 agent-layer split (every path in it is now
stale — it describes `~/agent-core` as live, which is the dead clone), and nine
`MEMORY.md` index files whose content is the entries themselves.

## Traps hit

- **My coverage matcher matched everything.** Normalising lesson titles to `[a-z0-9]` turned
  the CJK-titled ones into empty strings, and the empty string is a substring of every slug —
  so the first run reported 36 of 36 feedback entries as covered, all of them "matched" to a
  lesson about quiet observation windows. Guarding on `len(normalised) >= 8` gave the real
  answer: 16. **This is the lesson I had written to the factory an hour earlier, committed by
  the same session that wrote it.** A match is not coverage, and that applies to the tooling
  used to check coverage.
- **Then the same failure again, one layer up.** Topic-word probes reported the reference
  files as covered; per-file identifier probes (`PatientService.PatientSendCreateAccountEmail`,
  `pnsSend2faCodeEmail`, `valogin.controller.ts`) showed the PNS pipeline was entirely absent
  — four of five probes returned nothing. Topic words matched because `patterns.md` discusses
  Postmark and Kafka in other contexts.
- **A prod DB password sat in the store.** Archiving verbatim would normally be wrong, but the
  same credential is already hardcoded in 8 committed files under `DailyJob/`, so the archive
  adds no exposure. The schema facts were written forward without it, with a note saying so.
  The hardcoded credential itself is a separate finding, raised rather than fixed.

## Open

- `DailyJob/` carries a plaintext prod DB password across 8 committed files.
- The `~/personal/remote-agent/` instance still has auto memory unset in both its repos.
- ~~`project_emr_v2_git_hooks` records three guards living in `.git/hooks/`~~ — **closed the
  same day.** Leo chose `core.hooksPath`; the guards moved into the factory as tracked,
  repo-aware, chaining hooks wired globally (factory PR #41). While wiring it, the
  working-agent repo turned out to have a *local* `core.hooksPath` pointing at a directory the
  July rename deleted — its git hooks had been silently dead for six weeks, and a local setting
  overrides the global one, so it would have stayed dead. Same failure shape as everything else
  this rename caused: a path-derived assumption that fails by doing nothing.
