---
name: defect-found-must-be-ticketed
description: "Serious miss (Leo, 2026-07-27) — defects discovered during testing/E2E must become tracked tickets immediately; a \"proposed follow-up\" note in STM is not tracking"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 944b69a9-64b4-4892-a0d6-b929c2b24d20
  modified: 2026-08-06T17:28:57.415Z
---

During VP-17286 E2E (2026-07-13) the agent DISCOVERED that a terminal-failure placerId permanently blocks retry (scope item 7, "permanently stuck") and even wrote a proposed fix — but only as a note inside the STM file. No ticket was filed. Nobody scheduled it. On 2026-07-22 an external integration partner (api-product) hit exactly this in the sandbox; it took until 2026-07-27 (VP-17497) to fix. Leo: "這也是一個嚴重的失誤".

**Why:** memory notes have no owner, no status, no queue — they are invisible to planning. A known defect that lives only in a note is functionally an unknown defect, and the cost of rediscovery was paid by an external partner.

**How to apply:** the moment a test/E2E/triage surfaces a real defect that will not be fixed in the current ticket, file a Jira ticket for it in the same session (assign Leo, link the parent), then reference the ticket id in the STM note — never the reverse. When closing a ticket, scan its STM for "follow-up"/"proposed"/"wrinkle" phrases lacking a ticket id; each one is an unfiled defect. Related: [[audit-recently-done-tickets]].

**SCOPE BOUNDARY (Leo, 2026-07-28):** this rule applies ONLY to defects in OUR OWN scope (Leo's repos/services: emr-v2, transformer, etc.). For defects in ANOTHER team's service (e.g. the OAuth Rust service — VP-17522 was filed unilaterally and Leo objected: "以後這種不是我的問題不要隨便開ticket，我不是PM"), do NOT file a ticket. Instead: package the full diagnosis + evidence in the report to Leo and let him decide whether/where/who files it. Same discipline (don't let it die in a note), different mechanism (hand-off, not self-filing).

**BUG TYPE NEEDS LEO'S CONFIRMATION (Leo, 2026-08-06):** never file a ticket with issue type **Bug** without Leo confirming it is actually a bug first — "很多東西並不一定是這樣的" (VP-17503, filed as Bug from code inspection, was reclassified by Leo to Story/feature). When self-filing an own-scope finding, either ask Leo the type first, or file it as Story/Task/Improvement and note that Bug classification is pending his call. Filing itself is still mandatory (don't let it die in a note) — only the Bug label needs his sign-off.
