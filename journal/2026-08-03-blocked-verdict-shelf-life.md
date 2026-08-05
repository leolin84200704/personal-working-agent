---
date: 2026-08-03
slug: blocked-verdict-shelf-life
related_tickets: [VP-17537, VP-17538]
distilled: true
---

# VP-17537 closeout + Leo's process correction: blocked verdicts need edges and expiry tests

## Context
Leo asked "VP-17537 做完了嗎". I verified Jira (Dev To Do) + STM, reported the code was live on
prod but the live E2E was "blocked on charging ACH" — repeating the 7/29 STM verdict. Leo: "我們
不是有一個 ticket 會一直找到可以使用的信用卡為止嗎？3194 有一張可以用的" — VP-17538's
payment-method walk (live since 7/29 23:39Z) had removed that exact blocker 4 days earlier.

## What we explored
- Ran the E2E: api-sandbox POST /v1/orders (client vac_Quz5...3194, patient 3226441, GUT_ZOOMER,
  chargeIndicator C) → 201 placed, sample 2554034, accessionId 2608036004, order_intake 160.
- Walk proven live: pod log 3x ACH failures then "charge succeeded on fallback method #3
  id=366147 card/stax". staging tzdata issue did NOT reproduce.
- accession_id proof: charging minted julien_barcode 2608036004 pre-placement (row 160) and the
  place-order RESPONSE echoed it — order-management never calls charging, so the value can only
  have come from our payload. Response-echo-of-a-value-only-we-had = cheap payload proof pattern.
- Jira closed: Root Cause (10485 ADF) + Category=Code Defect (10490), transition 15.
- Earlier same session: recurring zymebalanz link complaint — the 7/31 file fix never reached the
  running WezTerm because dofile'd configs aren't reload-watched; touched main config + committed
  add_to_config_reload_watch_list to dotfiles (64a3642).

## Decisions
- Leo's diagnosis (verbatim intent): the failure was not a stale STM line — I didn't read related
  tickets; flat `links:` (55 untyped entries) gave no reason to. "link 的 process 有可以改善的空間".
- Approved 4-part fix, all via PR:
  1. blocked status must carry testable `unblock_when:`; re-test before repeating a verdict
  2. hand-curated `relations:` (unblocked_by/blocks/sibling) separate from auto `links:`
  3. dream Phase 0.5 dependency propagation (shipped ticket → RE-CHECK marker on dependents)
  4. status-question retrieval sweeps relations with newer `updated:`
- YAML comments in STM frontmatter don't survive memory_scoring.py's PyYAML round-trip — schema
  docs live in the factory template only.

## Files touched
- PRs: project-agent-factory#16 (template + framework RETRIEVAL), working-agent#19 (RETRIEVAL,
  dream.md, STM backfills: PLESSEN/BIOINSIGHTS/VP-17475 unblock_when, VP-17537/38 siblings)
- main direct: VP-17537/38 STM closeout + LTM emr-integration correction (990912c); dotfiles 64a3642

## Open questions / followups
- Both PRs await Leo review — do not merge.
- VP-17538 wallet-priority ORDER spec still unanswered (prod runs charging array order).
- charging payWithAch create-branch bug still open (charging team scope).

## User feedback this session
- "實際上是你沒有去看其他的相關 ticket issue, 對大方向不了解" — status answers must sweep causally
  related tickets, not just the asked-about one. Never repeat a blocked verdict without re-testing.
