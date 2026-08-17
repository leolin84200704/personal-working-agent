---
name: feedback-verify-deploy-with-two-signals
description: "My deploy watcher reported DEPLOYED while the pod was still 45h old — confirm with image SHA vs branch HEAD plus a code marker, and never report deploy status from one script's word"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8d79ed9c-df6d-4ef0-bbce-d58e1e48249f
  modified: 2026-08-12T20:04:05.814Z
---

2026-08-12: I told Leo a staging deploy had landed. It had not — the pod was still on the 45-hour-old image and none of the merged code was running.

Cause was my own polling script: `grep -c "MARKER" file || echo 0`. When grep finds nothing it prints `0` **and** exits 1, so `|| echo 0` fires too — output becomes `0\n0`, which after stripping whitespace is `"00"`, and `"00" != "0"` read as "marker found".

**Why it matters:** a false "deployed" makes every subsequent test result meaningless, and I reported it to Leo as fact. Same family as [[feedback-never-conclude-breakage-from-a-quiet-window]] — a single weak signal, taken at face value.

**How to apply:**
- Deploy verification needs **two independent signals that agree**: pod image tag == `git rev-parse origin/<branch>`, AND a marker string unique to the new code present in the running `dist`.
- Pick a marker that cannot exist in the old build. `generateBarcodeForSampleID` was useless — the old code contained it too; `grpcV1` was the discriminating one.
- In shell, read `grep -c` via its **exit code**, not by pattern-matching its stdout; never paper over it with `|| echo 0`.
- Re-verify by hand before reporting, even when a watcher says done.

Merging to a work repo's `staging` does not necessarily update the pod — deployments are pinned to a commit-SHA image tag, so a merge can sit unshipped. Check, don't assume.
