---
name: lis-code-agent workflow preferences
description: How Leo prefers to work with lis-code-agent — confirm requirements before coding, evaluate proposals before executing
type: feedback
originSessionId: a9c0a540-cd8a-4393-8a5f-f2aa8c05a1f9
---
When using lis-code-agent to process tickets, always present the analysis and proposed solution for Leo's review BEFORE executing code changes or creating branches.

**Why:** VP-15302 showed that ticket descriptions can be unclear and PM confirmation may change the scope entirely. The agent over-engineered a complex solution (bundle fallback + shortcut API + new model) when the actual requirement was much simpler. Multiple rounds of correction were needed.

**How to apply:**
- Always have the agent do analysis-only first, then wait for Leo's confirmation
- When Leo says "先不要執行" — strictly analysis only, no branches, no code changes
- When requirements come from PM clarification, expect them to be simpler than what the ticket implies
- Leo will provide the correct business logic when the agent's proposal is wrong — incorporate his corrections precisely
- After Leo confirms, let the agent execute and show the diff for final review
