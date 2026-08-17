---
name: feedback_sync_sibling_encodings
description: "When changing a value/boundary's semantics, sync every sibling derivation in the same function and don't mock away the shared code path in tests"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 23f07ed0-099e-43b4-b44c-55a1b8e6fc59
---

When you change the **semantics** of a value/boundary, first enumerate every place in the **same function/flow** that derives from it or must agree with it (display value, validation cutoff, query window, forward/backward search bounds, downstream math) and change them together — ideally compute once via a single source and reuse. Local symptom-patching the one flagged line leaves siblings inconsistent.

**Why:** VP-17260 `getBookingRules` encoded the max-advance booking boundary in 3 places; changing one (`validateBookingTime` → `maxAdvanceCutoff`) without the others caused Bugbot to flag the same class of bug twice — including one I introduced while fixing the first, with the inconsistent line ~10 lines above my edit in the same function I had open.

**How to apply:** (1) Before editing the boundary, grep/read the whole function + flow, list co-dependent uses, migrate all in one PR from a single source. (2) In the test, do NOT mock away the code path that shares the invariant — my Finding-1 test mocked `findMany → []`, hiding the exception-window bug and giving a false green. Pick a case that actually exercises the interacting path (e.g. a time where the rolling day ≠ the cutoff day) so old code fails and new code passes. Smaller-scope cousin of [[feedback_migrate_all_readers_no_mirror]] and [[feedback_audit_callers_when_adding_fallback]] — here the miss was inside a single function.
