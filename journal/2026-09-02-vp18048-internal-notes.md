---
date: 2026-09-02
tickets: [VP-18048]
type: journal
summary: "VI appointment Internal Notes — BE done on a worktree branch, local commits, awaiting Leo's review before push; migration not yet applied."
---
# 2026-09-02 — VP-18048 Internal Notes (transv2 calendar)

## Shape of the session

Leo handed the ticket with the one open question already answered: internal user
= any role that is not patient, and "check whether we need to add a few columns".
Explore agent mapped every surface a `v2_event` column can leak through; the
answer was narrower than the ticket's fear: GraphQL `Event` is explicit-@Field
plus an explicit mapper, every email template model and Google/Outlook/Zoom
payload is hand-picked, there is no `.ics` anywhere. The only implicit spread is
the Kafka `addon_column` in two services. Persistence gaps were the explicit copy
lists: clinician-switch rebook and THIS_AND_FUTURE split.

## Decisions worth remembering

- Read gate as a `@ResolveField` on `EventResolver`, Event has no `@Field` for
  it. Chosen over a viewer flag on `mapEventToGraphQL` (14 call sites) because a
  forgotten flag is invisible and a missing field resolver is not.
- Two columns, not one: `updated_internal_notes` on `v2_event_exception` so a
  THIS_EVENT edit is not a silent no-op — the "update contract vs handler
  consumption" lesson applied before the bug existed.
- `rescheduleClinicalConsult` had no patient-token check at all. The new
  `assertCanWriteInternalNotes` covers the new field there; the pre-existing gap
  is noted in STM, not fixed (out of scope).
- PH-822 (no-email-on-non-time-edit) is not started; the AC that depends on it is
  flagged, not faked.

## Friction

- Worktree needs `.env` symlinked as well as `node_modules` — three suites
  failed to *load* on a missing Kafka env var before any test ran.
- The manual-migration apply-script convention (`scripts/vp-*-apply-migration.js`)
  and one migration SQL exist only as untracked files in Leo's main checkout.
  Copied the pattern and committed this ticket's copies.
- Four calendar suites fail on clean origin/main (live DB + practice-event-type
  GraphQL specs). Checked with `git stash -u` before believing they were mine.

## State at close

Branch `feature/leo/VP-18048` in worktree `LIS-transformer-v2.worktrees/VP-18048`,
2 local commits on top of `bea60c6`, not pushed. 94/94 targeted tests, build OK.
Migration written, not applied. Jira draft in `drafts/VP-18048-open-questions-draft.md`.
Waiting on Leo: push/PR go-ahead, migration go-ahead (dev_new then prod, before
deploy), and the three PM confirmations (role model, 2000 cap, PH-822 stop-gap).
