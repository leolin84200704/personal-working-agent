---
name: feedback_migrate_all_readers_no_mirror
description: "When swapping a value's source-of-truth, migrate EVERY reader (incl generic DTO mappers) and stop writing the old store — don't keep mirroring it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 25da76b7-c932-4728-aedf-05b96b1a128c
---

When migrating a field's source of truth (e.g. timezone DB column → provider setting service): (1) migrate **every** reader, not just the obvious dedicated getter — include generic/shared DTO mappers and serializers (e.g. a `mapToGraphQL` that builds the whole settings object); (2) once nothing reads the old store, **stop writing it** — do not keep "mirroring" the deprecated column for safety.

**Why:** two real defects caught in VP-17190 PR review:
- I migrated the dedicated `getTimezone` + booking-rules to the new setting but missed the generic `mapToGraphQL` used by `getUserSettings`, which kept returning the mirrored/stale column → queries disagreed.
- I kept dual-writing the deprecated `v2_calendar.timezone` "to keep the mapper in sync". Since the setting is the sole authority and is also written elsewhere (FE login capture) without touching the column, the mirror diverges; and writing two stores in one method is a non-atomic gap (setting write succeeds, column write fails → inconsistent).

**How to apply:** grep ALL readers of the field (including mappers/`*.toGraphQL`/serializers/response builders), migrate them to the new source, then the mirror write becomes provably dead — remove it. A mirror that nothing reads only adds divergence + atomicity risk. Column drop is the separate cleanup, but stop the writes once readers are gone. Related: [[feedback_join_scope_reverse_audit]], [[feedback_audit_callers_when_adding_fallback]].
