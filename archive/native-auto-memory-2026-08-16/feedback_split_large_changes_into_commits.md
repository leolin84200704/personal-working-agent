---
name: feedback-split-large-changes-into-commits
description: "Large/multi-concern changes must be split into at least 3 commits, not one big commit"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ace3c9f4-1cde-4627-b7ea-a5510e69886f
  modified: 2026-07-30T23:18:58.300Z
---

Leo, 2026-07-30 (after VP-17559 landed as one 773-line commit touching service + listener + configmap
template + 2 AKS manifests + deps): any sizable change must be split into **at least 3 commits**.

**Why:** a single fat commit makes a specific mistake hard to correct and hard to revert — you cannot
back out the risky part (e.g. the k8s manifest / prod config slice) without also reverting the safe
part (e.g. the new service + its tests).

**How to apply:** plan the commit boundaries BEFORE writing code, and split along revert boundaries —
each commit independently revertible and independently reviewable. For a change like VP-17559 that is
roughly: (1) new capability + its unit tests (no wiring, inert), (2) wire it into the caller /
behavior change, (3) infra & config (configmap/deployment/manifests, deps). Keep the risky-to-revert
infra slice last and alone.

Note the constraint this creates: once a branch is pushed, splitting retroactively needs history
rewrite, and force-push is forbidden in the LIS work repos ([[work-repos-staging-before-main]]) — so
either get the boundaries right the first time, or re-create the branch under a new name with a new
PR rather than force-pushing. Related: [[always-share-pr-link]], [[distill-to-factory-habit]].
