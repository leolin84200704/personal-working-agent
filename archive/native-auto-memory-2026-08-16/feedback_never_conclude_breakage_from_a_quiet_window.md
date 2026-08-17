---
name: feedback-never-conclude-breakage-from-a-quiet-window
description: "SEVERE 2026-07-31 incident: I rolled back a WORKING prod cutover because one quiet observation window looked like breakage, causing ~17 duplicate result deliveries"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ace3c9f4-1cde-4627-b7ea-a5510e69886f
  modified: 2026-07-31T02:17:29.965Z
---

**2026-07-31, VP-17561 — my worst call of the session. Do not repeat it.**

I cut emr-v2's result-event consumption from on-prem Kafka to the cloud Event Hub. It worked. I then
declared it broken and rolled it back, which replayed 1,940 on-prem messages and — because result
push has no idempotency gate ([[result-push-has-no-idempotency-gate]]) — **re-delivered result ORUs
for ~17 samples** (mostly MDHQ, some PF/ATHENA) to real EMR vendors.

**What I actually did wrong: I concluded "broken" from a single quiet observation window.**
At 01:25 (61 min after the cutover) I measured zero new `result_transmission_records` and treated
that as proof of breakage. The upstream simply had no `report_finished` events between 00:24 and
01:29 — a gap I had *already documented myself* ("18:00=0, 21:00=0 pre-cutover, so a zero hour is
not unprecedented") and then ignored when it was my own change under suspicion. Events resumed at
01:29 and the cloud pod processed them correctly: 35 records, all TRANSMITTED, one of them
(sample 2602738) stamped with the cloud pod's own name — proof it worked, available 5 minutes before
I rolled back.

**The compounding error:** I built a confident statistical case (64 events × 19% expected hit rate,
"p ≈ 1.6e-6") on top of an assumption I never checked — that those 64 events had *already arrived*
during the silent hour. Their timestamps were all 01:29–01:31, i.e. after my zero measurement. Rigor
applied to the wrong premise reads as certainty and gets you to act.

**Rules I owe from this:**

1. **A quiet window is not evidence of failure.** Before calling a change broken, measure the input
   side: did the work the system consumes actually arrive during the window? For a queue/topic, that
   is `fetchTopicOffsetsByTimestamp` + consumer-group lag — lag ≈ 0 means the system consumed
   everything available, i.e. it is healthy and the input was empty.
2. **Check whether the alleged failure has an alternative explanation you already documented.** If I
   have written down "zero hours happen here", my own change is not exempt from that baseline.
3. **Verify timestamps of the evidence, not just its count.** 64 events "since the cutover" said
   nothing until I looked at *when* each arrived.
4. **Rollback is a prod change with its own blast radius.** For a consumer-group switch, rolling back
   replays everything the idle group missed. Before switching either direction, advance the target
   group's committed offset to the high watermark (`admin.setOffsets`), or accept duplicate
   deliveries. When I re-enabled cloud, the cloud group had 8,501 lag queued; advancing it first
   avoided a second duplicate wave.
5. **Escalate before acting when the "fix" is itself risky and the user is right there.** Leo was in
   the conversation. Reporting "0 records for an hour, here is what I would check next" costs one
   message; an unnecessary rollback cost 17 duplicate patient-result deliveries.

Related: [[audit-recently-done-tickets]] (Done ≠ verified — same family of error, opposite direction),
[[execute-not-just-verify]] (bias to act is right for *reversible* diagnosis steps, not for prod
state changes built on one measurement).
