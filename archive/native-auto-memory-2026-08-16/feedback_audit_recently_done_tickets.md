---
name: audit-recently-done-tickets
description: After VP-17474 incident — closely monitor tickets completed within 24h; Jira Done ≠ deployed/verified; check the whole closure chain
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1cd1f5c7-3cc0-4ed1-8651-aee0a33cb4ca
  modified: 2026-07-22T22:20:18.888Z
---

Leo (2026-07-22, after the VP-17474 incident): "這是嚴重的失誤，以後請你要密切關注 24 hr 以內完成的 ticket，確保每個環節都沒有出錯."

**Why:** VP-17474 was marked Done in Jira while prod was actively broken for ~20h: code requiring a manual DDL was promoted to main (auto-deploy) without the DDL, silently killing result-ready emails (265 lost) and 500ing all deep links. Two traps made me misreport it as "not yet deployed": (1) promotion PRs were titled "Stage test" — searching PRs by ticket id missed them; (2) I trusted the plan ("DDL awaiting approval") instead of probing prod state.

**How to apply:**
- For any ticket transitioned to Done/completed in the last 24h, verify the full closure chain before treating it as solved: PRs merged (search by ticket id AND scan recent merges to auto-deploy branches — promotion PRs often carry no ticket id) → deploy workflows green → manual prerequisites (DDL/env vars/config in PR body) actually applied on staging AND prod → post-deploy health signals clean → live verification AFTER the final deploy exists in STM.
- "Requires manual step before deploy" in a PR body is a red flag: verify the step happened, don't assume.
- Automated nightly closeout audit lives in the dream pipeline (see [[distill-to-factory-habit]] repo PR flow); if it flags a ticket, escalate to Leo immediately.
- Related: memory says verify against ground truth ([[verify-sample-core-not-emr-mirror]] spirit) — prod DB/endpoint probes beat any document.
