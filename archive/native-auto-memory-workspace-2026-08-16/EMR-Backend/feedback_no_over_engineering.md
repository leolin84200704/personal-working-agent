---
name: No over-engineering — confirm requirements before coding
description: VP-15302 lesson — always confirm unclear ticket scope with PM before proposing complex solutions
type: feedback
originSessionId: e347efec-ad1a-4826-bc5f-1da577b2d0bd
---
When a ticket description is unclear, do NOT start extensive code analysis and propose complex solutions. Ask Leo to confirm precise requirements with PM first.

**Why:** VP-15302 had vague AC. Agent did deep code analysis and proposed a complex plan (bundle fallback, shortcut API fallback, new model classes). PM later confirmed the actual need was simple: bundle matching with clinic_id comparison. Wasted significant effort.

**How to apply:**
- If ticket AC is ambiguous, ask Leo to clarify with PM before starting implementation
- Do not infer or expand AC scope on your own
- Default to the minimal change first, then expand after confirmation
