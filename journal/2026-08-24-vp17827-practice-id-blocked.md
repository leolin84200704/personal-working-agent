---
date: 2026-08-24
slug: vp17827-practice-id-blocked
related:
- VP-17827
- VP-17826
- VP-16163
- VP-16164
- VP-16165
- VP-16166
- QH-6775
- HL7-NPI-PRACTICE-MATCH-20260820
distilled: false
---

# 2026-08-24 — VP-17827 practice ID on EMR order placement: analysed, commented, blocked

Related: VP-17827, VP-17826, VP-16163, VP-16164, VP-16165, VP-16166, QH-6775,
HL7-NPI-PRACTICE-MATCH-20260820

## What happened
- Leo opened the session with just the ticket id: `VP-17827`.
- Ticket read as an ordinary Story in **Dev To Do**: accept / validate / persist a practice ID on
  the EMR order placement path. It looked like a straightforward field addition.
- After retrieval + code reading + walking the Jira link graph, the verdict was: **not buildable**,
  and the ticket's own premise needed correcting. Reported at WORK-LOOP Step 4 without writing code.
- Leo: `先comment 然後改成dev block`. Posted comment 185290 (English) and moved the ticket
  Dev To Do -> Dev In Progress -> **Dev Blocked**.
- Leo closed with `done`. Wrote retrospective + this journal, committed the memory backlog that had
  been aborting the dream pipeline for three nights.

## What I explored
- **Memory first.** STM/LTM/journal `_index.md` all read `Last updated: 2026-08-20` — over the
  3-day staleness threshold, so I chased that separately (see below) and treated index scores as
  unreliable, grepping instead.
- Grepping STM for `practice.id` surfaced ~20 files, but the load-bearing one was
  `HL7-NPI-PRACTICE-MATCH-20260820.md` (15KB, updated 08-21) — the record of Leo's decision to
  match HL7 orders on `customer_npi + practice_id`, the prod inventory, four executed prod changes,
  and a per-vendor measurement of which HL7 field actually carries a practice.
- `reference/hl7-practice-field-by-vendor-20260821.csv` — 54 rows of (vendor, MSH-4, sent clinic,
  order count, what MSH-4 actually is). This is the single most valuable artefact for this ticket.
- Code: `lis-backend-emr-v2` at `origin/main` (ebb104f). The working checkout sits on
  `feature/leo/VP-17342` with uncommitted work and is behind main, so I made a detached read
  worktree at `~/src/lis-backend-emr-v2.worktrees/vp17827-read` rather than disturb it or read
  stale files. Removed at the end.
- Jira: the ticket, its blocker, and — the step that actually mattered — **all children of the
  parent epic VP-16163**.

## What I ruled out and why
- **"Just add the field and key on it."** Ruled out by prod counter-example: clinic 6212's two
  2026-08 orders carry MSH-4 = another customer's id and succeed today; keying on `(npi, MSH-4)`
  turns them into `customer_not_found`. Practice must be a layered check on top of the existing
  ORC-12 resolve, never a replacement. This was already recorded in the 08-20 STM as a
  "conclusion correction" — retrieval saved me from re-deriving it the expensive way.
- **Designing the layered fallback now and presenting it as the plan.** Ruled out because no test
  plan can be written: the acceptance behaviour for both failure cases is an unmade product
  decision, so any test would assert semantics I invented. WORK-LOOP's rule that a plan without a
  test plan cannot enter Step 5 is what stopped me. Naming this explicitly because the pull toward
  "look productive, produce a design" was the strongest force in the session.
- **Treating the ticket as routine config work.** Ruled out: it is a code change to the order
  intake path, on a new pattern, affecting prod order routing. Highest risk class.

## Why the conclusions came out this way
- The decisive move was reading the epic's children, not the ticket. **VP-16164 "[BE] Practice-Level
  Integration Data Model & Migration" is Inactive** — that is the table the story's "persist practice
  ID on the order record" criterion needs, and the code comment in
  `hl7-order.processor.ts:364-500` literally says its practice branch "will move to
  practice_integrations once VP-16164 lands". So one of four acceptance criteria has no target at
  all, and nothing on VP-17827 itself says so.
- VP-16165 (identity resolution cascade) is Done and VP-16166 (quarantine) is Dev To Do, which
  places VP-17827 in the middle of a pre-existing designed sequence whose two ends are stalled.
- The blocker VP-17826 is Dev Blocked with a Jira automation comment from 08-21 asking Leo for
  blocker details, unanswered. Meanwhile its actual deliverable (vendor x provider x NPI x clinic
  list with multi-clinic NPIs flagged) was already produced on 08-20/21 and sits in `reference/`.
  The blockage is outreach, not analysis.
- The premise correction rests on measurement, not opinion: 5 of 6 active vendors send no practice
  field; ~24% of orders carry anything we recognise as a clinic; FOLLOWTHATPATIENT already sends the
  Vibrant clinic_id twice (MSH-6 + ORC-17) and we read neither, with one confirmed mis-routed order
  (sample 2597376, July, booked to 2930 instead of 36290 because customer 43262 spans 4 clinics).
- Lesson injection (Step 1.4) picked **"Owner-scoped, not actor"** — the clinic is being derived
  from the ordering provider (actor) instead of the practice that sent the order (owner), which is
  the defect in one line — and **"Caller 能自己修正的失敗要回 4xx"**, which governs the PM's second
  open case: a non-matching practice ID is a rejection with a quotable reason in the vendor's own
  vocabulary, not a 5xx and not a silent reroute.

## Leo's own words
- `VP-17827` — the entire opening prompt.
- `先comment 然後改成dev block`
- `done`

## Mechanics worth keeping
- **Dev To Do has no direct edge to Dev Blocked** in the VP workflow. Transitions out of Dev To Do
  are only Inactive / Done / Dev in progress. Dev Blocked is reachable only via **Dev In Progress**
  (transition 3, then 4), so the issue history shows a momentary pass through Dev In Progress. Not
  an error — check `getTransitionsForJiraIssue` on the intermediate state before concluding a
  status is unreachable.
- Writing the blocker comment in the exact two-part shape the VP automation asks for
  ("What's blocking" / "What is needed to unblock") also pre-empts the bot firing the same request
  again on the transition.
- Standing rule tension recorded: instance CLAUDE.md says Jira comments are drafted, not sent. Leo's
  instruction overrode it for this comment. There is no edit/delete-comment tool available through
  the Atlassian MCP, so a posted comment can only be corrected by Leo in the Jira UI — which is
  itself the reason the draft-only rule exists.

## Side finding: the dream pipeline had been down three nights
- `logs/launchd-stdout.log`: 08-21, 08-22 and 08-23 each ended with
  `ABORT: uncommitted changes to tracked memory files — storage/short_term_memory/VP-17812.md`.
  Last good run 08-20. That is the whole explanation for the stale `_index.md` dates.
- The uncommitted diff was legitimate finished work (the 08-21 Prospera requisition deep-dive,
  +63 lines) plus a re-sorted reference CSV. Nothing to decide; it just needed committing.
- The guard reads only TRACKED files, so new untracked STM files do not trip it.
- The guard's own comment says "a dirty memory file is a signal, not an obstacle" — but as written
  it is an obstacle with no escalation. One forgotten commit stops the entire distillation layer
  indefinitely, and the only symptom is a date inside a file nobody re-reads. The CLAUDE.md
  staleness check caught it three days late; that is the backstop working, but late.
- Candidate for a factory lesson PR: **a guard that refuses to run on a dirty tree needs an
  escalation ladder** — abort once, then on the second consecutive abort notify loudly or degrade to
  a read-only run, so the failure cannot stay silent for more than one night.
