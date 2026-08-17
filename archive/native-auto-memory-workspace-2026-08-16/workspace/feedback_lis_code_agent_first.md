---
name: Always reference lis-code-agent repo first
description: For all LIS-related work, consult /Users/hung.l/src/lis-code-agent before acting — it is the source of truth for workflow, knowledge, and STM
type: feedback
originSessionId: c6cdf891-d6ac-470e-b74a-fe1d6458898a
---
Before starting any LIS-related ticket or task, always consult `/Users/hung.l/src/lis-code-agent` first.

**Why:** Leo has built a structured agent system there (CLAUDE.md defines Work Loop, knowledge/ holds routing + domain knowledge, storage/short_term_memory/ holds per-ticket records, skills/ holds reusable flows). Skipping it means duplicating effort, losing past lessons, and bypassing the agreed 9-step Work Loop.

**How to apply:**
- Start every LIS ticket by following the Work Loop in `/Users/hung.l/src/lis-code-agent/CLAUDE.md` (Step 1 Retrieve → Step 9 Memory Update).
- Grep `lis-code-agent/storage/short_term_memory/` for similar past tickets before analyzing.
- Route via `lis-code-agent/knowledge/ticket-routing.md` to find the right knowledge file.
- Write STM to `lis-code-agent/storage/short_term_memory/{ticket_id}.md` as work progresses.
- Pause at Step 4 (plan confirmation) and Step 6 (review) for Leo's approval — do not auto-advance.
