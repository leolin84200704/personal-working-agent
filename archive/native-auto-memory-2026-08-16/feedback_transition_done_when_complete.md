---
name: transition-done-when-complete
description: Leo authorized (2026-07-27) auto-transitioning Jira tickets to Done once work is complete and verified; VP Bugs require Root Cause fields first
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 944b69a9-64b4-4892-a0d6-b929c2b24d20
  modified: 2026-07-27T21:58:13.575Z
---

Leo: "完成了話直接改成done" — when a ticket's work is complete AND verified (merged, deployed, live-verified per the closure chain), transition it to Done directly instead of leaving transitions to Leo.

**Why:** removes a hand-off step Leo doesn't want; "complete" still means the full closure chain from [[audit-recently-done-tickets]], not just code pushed.

**How to apply:** transition id 15 = Done in the VP workflow. VP **Bug** issues are gated: `Root Cause` (customfield_10485, ADF doc — plain string is rejected, wrap in {type:"doc",version:1,content:[paragraph]}) and `Root Cause Category` (customfield_10490, option e.g. "Code Defect", "Requirements / Design Flaw") must be set via editJiraIssue BEFORE the Done transition. Stories have no such gate. Outstanding sub-items that survive closure (e.g. a deferred migration part) must be tracked visibly elsewhere (PR body, follow-up ticket, or promotion checklist), not implied by the open ticket.
