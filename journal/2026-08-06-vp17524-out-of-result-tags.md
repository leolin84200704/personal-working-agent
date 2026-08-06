---
date: 2026-08-06
slug: vp17524-out-of-result-tags
related: [VP-17524]
distilled: false
---

# VP-17524 — the OUT_OF_ prefix, and reading a symptom one layer too early

Leo handed me the bare ticket key and nothing else. Ticket was self-filed by the dream scan on
2026-07-28, still Dev To Do, no comments.

## What I explored

Started from the prod pod rather than the code, because the ticket's frequency claim (~10 ERROR/day)
was worth checking against the current image. 15h of `lis-emr-v2-deployment-prod-7dc786b5c5-jsnz2`:
1650 mapping calls, and the two `OUT_OF_RESULT_NORMAL` errors were the *only* ERROR lines in the
whole window. The tag distribution was the useful part — every other tag carried an `_M` suffix and
`OUT_OF_RESULT_NORMAL` did not, which is a hint that it comes down a different path.

Grepping the log context around the error gave me the case in full, which was better than anything
I could have reasoned out: test 76 EGFR, masterlistId 2257, rawResult 93.41, latestTestValue ">90",
range "60-90". An eGFR above 90 is normal kidney function. It was being delivered as if the test had
not been run.

## What I ruled out

**"Ask the lab/report team what this type means"** — the ticket's own proposal. I dropped it after
finding the convention encoded in three places across two other repos: LIS-Report's `util.ts`
*produces* the tag off the ±999999 reportable-range sentinel plus the direction of the open-ended
normal range; LIS-Report's `result-common.service.ts` *consumes* it grouped with `RESULT_NORMAL`;
report-pdf's `FoodSummaryService.js` groups `OUT_OF_RESULT_HIGH_ABNORMAL_M` with
`RESULT_HIGH_ABNORMAL_M`. Three independent votes for "the prefix is a range annotation, the
suffix is the clinical class". A human round-trip would have been slower and less certain.

**"Legacy Java has no mapping for this either, so maybe the type is new upstream data"** — also from
the ticket. Wrong framing. Java has no mapping because Java never received a tag at all:
`MasterListClass.parseResult2SampleTestStatus()` takes the *value* and walks the reference range
list. Running it in my head on ">90": `replaceAll("<|>","")` → 90.0, matches 60~90 → `RESULT_IN_RANGE`
→ `N`. So legacy Java delivered `N` for this exact result and the fix is a parity restoration, not a
new behavior. That single fact decided the ticket.

The real root cause is the porting shift nobody wrote down: Java *derived* the classification,
emr-v2 *trusts a precomputed label from gRPC*. The moment you start trusting someone else's
vocabulary, an enumerated switch is guaranteed to be short.

## Where I was wrong

I wrote the original ticket, and I got the symptom wrong in it: "HL7 OBX-8 abnormal flag TNP".
Following the flag into `hl7-encoder.service.ts` shows `abnormalFlag === 'TNP' ? '' : abnormalFlag`
on OBX-8 — so the flag is *blanked* — and separately, line 181, TNP appends an
`NTE|1||Test Not Processed` segment. Blank field plus an explicit "not processed" note. I had stopped
reading at the variable instead of at the wire. Same severity, different artifact, and the NTE is the
part a human at the clinic actually reads.

## Decisions

Offered Leo three options: minimal (`case 'OUT_OF_RESULT_NORMAL'`), systematic (strip the `OUT_OF_`
prefix in normalization), and "soften the `default:` branch". Recommended the middle one, rejected
the third outright — failing closed on a genuinely unknown tag is correct, and that ERROR log is the
only reason this bug was ever visible. Leo: "ok 請直接改".

Naming detail that matters: base tags are `RESULT_NORMAL` / `RESULT_HIGH_ABNORMAL`, so the prefix to
strip is `OUT_OF_`, not `OUT_OF_RESULT_`. Getting that wrong would have produced `NORMAL`, which
matches nothing.

## The E2E Leo asked for

"先 end to end 測試完" — and this is the part I would not have done unprompted. The laptop has no VPN
(both gRPC hosts `nc` CLOSED), so I port-forwarded the three upstreams the prod configmap names,
generated `.env.local` from that same configmap with the hosts rewritten to localhost, and booted
the service locally as `POD_ROLE=web` + `ENABLE_KAFKA_CONSUMER=false` — which registers no intake
providers, no pusher queue processor, and no Kafka subscription, so it cannot touch prod work.
`POST /result/generate-content/:sampleId` is read-only by construction (`send_result:false`, gRPC
gets + `findFirst` only); confirmed zero files under `HL7_LOCAL_ROOT` afterwards.

Then: run patched, revert the one file, rebuild, run unpatched, diff. Same samples, same upstreams.

```
2608314: NTE 4 -> 3, 3 changed lines
  -OBX|18|NM|EGFR^eGFR||>90|mL/min/1.73m2 |60-90||||F|||20260806055142|
  -NTE|1||Test Not Processed
  +OBX|18|NM|EGFR^eGFR||>90|mL/min/1.73m2 |60-90|N|||F|||20260806055142|
2608325: same shape
2608429 / 2608473 / 2608305 (controls): 0 changed lines
```

The controls are what make this evidence rather than a demo. "The thing I wanted changed" is easy;
"and nothing else moved" is the claim that needed proving.

One incidental finding I like: `EGFRAA` (the African-American eGFR variant) on the *same samples*
with the *same* `>90` value already carried `N` in both runs. Its normal range renders as `>=60`
(open-ended), so the report pipeline tagged it `RESULT_NORMAL_M`; only the `60-90`-rendered `EGFR`
got `OUT_OF_RESULT_NORMAL`. The tag depends on how the range string was rendered, not on the value.
That is a fragile coupling living upstream of us, and worth remembering the next time a tag looks
inexplicable.

## Leo's words

- "ok 請直接改"
- "先 end to end 測試完 2. 不用repush" — so historical mis-delivered results stay as they are.
- "ok" (to commit + push + PR)

## Outcome

PR https://github.com/Vibrant-America/lis-backend-emr-v2/pull/324 (draft, base `staging`),
commit `68cb801`. `npm test` 97/97 suites / 1127 passed, `npm run build` clean. Jira → Dev Complete.
Still owed: the same check on staging after deploy, then prod — the local run proves the generator,
not the deployed artifact.

## Two small tool scars

- `npx jest` on a fresh worktree fails 5 suites for a missing `.prisma/test-client`; the `pretest`
  hook is what creates it. Use `npm test`. I nearly reported a phantom regression.
- zsh aborts `grep -r --include=*.java` with `no matches found` when the pattern is unquoted — which
  reads exactly like "the legacy repo has no such code". Quote it.
