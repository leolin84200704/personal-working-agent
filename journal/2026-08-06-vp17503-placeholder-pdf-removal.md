---
date: 2026-08-06
slug: vp17503-placeholder-pdf-removal
related: [VP-17503, VP-17493, VP-17342]
distilled: true
---

# 2026-08-06 — VP-17503: remove whole-order placeholder-PDF fallback

Related: VP-17503, VP-17493, VP-17342

## What happened
- Leo opened with two process corrections before the ticket: (1) the Atlassian MCP SSE-deprecation banner must never be relayed again ("已經講過很多次了我沒法做，你沒把這件事情記起來") — saved to auto-memory; (2) tickets must not be filed as type **Bug** without his confirmation ("很多東西並不一定是這樣的") — appended to the defect-found-must-be-ticketed memory. VP-17503 itself was the trigger: I had filed it as Bug from code inspection during VP-17493; Leo reclassified it Story ("這也不是bug") + Dev To Do. Note: VP project has no "Feature" issue type — Story is the closest (its Jira description literally says "features"); offered Improvement as alternative, no objection.
- Then "可以開始做VP-17503".

## Reasoning trail
- Explored origin/staging `result-generation.service.ts`: the entire fail-loud machinery already existed — `generateResultHl7` catch marks GENERATION_ERROR (category/code/message, retry_count, next_retry_at) and returns success:false; VP-17342 processor throws on success:false → BullMQ retry. So option A (throw) needed zero new mechanism; the change is almost pure deletion (-98/+32).
- Ticket posed A (throw+retry) vs B (data-only+flag) "for discussion" → Step 4 pause honored via AskUserQuestion; Leo picked A (recommended). Key argument against B: whole-order is the *authoritative* PDF delivery (VP-17493's own design comment) — degrading it means nobody ever delivers the PDF; B also needs schema change.
- Simplification: with whole-order also throwing, `throwOnFailure` had no remaining false-callers → removed the option entirely instead of flipping a default. Partial path keeps its call-site catch (data-only degrade) + `maxDownloadRetries: 0`.
- Deliberately NOT touched: `getClientConfiguration`'s 999997/10136 test-account branch — looks similar to the 2099046 PDF fallback but is client-config for reference-HL7 spec fixtures, different concern.
- Tests: replaced the two specs that asserted the legacy placeholder behavior (one was literally named "whole-order regression" guarding the OLD behavior); added whole-order propagation test (encodeResult never called on PDF failure). Full suite 96/96, 1093 pass.

## Outcome
- PR #322 draft → staging: https://github.com/Vibrant-America/lis-backend-emr-v2/pull/322 (single commit 51fdb8d; small coupled change, no split needed)
- Jira: Story, Dev In Progress. Worktree removed after push (per feedback memory).
- Awaiting Leo review; post-deploy live-verify = watch for GENERATION_ERROR records behaving as designed during any real PDF outage.

## Lessons
- When a "for discussion" ticket's options differ in product semantics, compress Step 3/4 into one AskUserQuestion with a recommendation — Leo answered in seconds; no debate subagents needed for a deletion-shaped change riding proven machinery.
- Self-filed tickets: classification (Bug vs Story) is Leo's call, not mine — the finding itself was correct and appreciated enough to schedule, but the label carried process weight (VP Bugs require Root Cause/Category fields; also team bug metrics).
