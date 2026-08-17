---
name: feedback-always-share-pr-link
description: "Every mention of a PR carries its full URL — not just the turn that opened it"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 693a8c46-ab8d-495d-a0bc-7a4502e35e85
  modified: 2026-08-03T22:27:09.872Z
---

Every time I reference a PR in a report to Leo, the full
`https://github.com/.../pull/N` URL goes with it — proactively, every time.
**This applies to every mention, not only the turn that opened it.**

**Why:** told twice.
- 2026-07-15: "以後都要給我PR連結" — I had reported PRs by number only (VP-17421
  #562, VP-17422 #536) and he had to keep asking.
- 2026-08-03: "PR 19在哪，以後都要附上連結" — I *did* include the links in the
  turn that opened factory PRs #17/#18/#19, then referred to "PR #19" bare in a
  later turn when reporting a correction to it. A bare number is unusable: he
  cannot click it, and finding it means guessing which of several repos it lives
  in (work repo vs project-agent-factory).

**How to apply:** treat "#N" as an incomplete reference — expand it inline every
time. When a turn touches several, list them all with URLs (PR + related Jira
keys as full links too). Repo matters: work PRs live under
`github.com/Vibrant-America/<repo>`, factory lessons under
`github.com/leolin84200704/project-agent-factory`, so the number alone is
ambiguous across them. Related: [[feedback_distill_to_factory_habit]].
