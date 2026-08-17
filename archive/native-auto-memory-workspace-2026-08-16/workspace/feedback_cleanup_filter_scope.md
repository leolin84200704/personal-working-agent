---
name: feedback-cleanup-filter-scope
description: "When deleting test/audit rows in prod, every WHERE clause must explicitly bound scope to the current session (time + explicit ID list); never delete by recipient_email or other broad attribute alone"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e78e7f19-dcbb-4fd1-b53c-f44060c07bd3
---

When cleaning up after a prod test (or any DELETE in prod), every WHERE
clause must explicitly bound the scope to *the current session's artifacts*.
Two safe filters to combine:

1. **Time bound** — `created_at >= NOW() - INTERVAL <short>` matching the
   test window (e.g. last 5–30 min).
2. **Explicit ID / pattern list** — `id IN (<cuid1>, <cuid2>)` captured
   from the test itself, or a pattern like `clinic_name LIKE '%VP16629_E2E_%'`
   that you authored and know is unique to your run.

Never delete by a single broad attribute (recipient_email, clinic_id,
customer_id, …) without one of those scopes attached. Those attributes
collide with historical legit rows.

**Why:** during VP-16629 cleanup I ran
```
DELETE FROM emr_integration_email_notification
WHERE recipient_email = 'hung.l@zymebalanz.com' OR recipient_email LIKE 'vp16629-e2e%'
```
as a "force cleanup" after some Prisma `$queryRaw` DELETEs returned
ambiguous `[]` results. The query matched a real 2026-02-02 audit row
(integration `cml5l2new00010xxs4j9rjqut`, "Test Clinic for Email")
because that integration had also emailed `hung.l@zymebalanz.com` months
earlier. The integration row itself survived, but a historical audit
entry was lost. Leo had to be told.

**How to apply:**
1. Before running prod DELETE, capture the explicit integration ids /
   timestamps from the current test run into a variable.
2. Always include either `created_at >= NOW() - INTERVAL <recent>` *or*
   `id IN (...)` in every DELETE — even the "force cleanup" fallback
   that runs when an earlier DELETE returned an ambiguous result.
3. If `$queryRaw` DELETE returns `[]` and you're unsure whether it
   succeeded, **don't widen the filter** to compensate — re-query with
   the same narrow filter to confirm, or use `$executeRawUnsafe` which
   returns affected-row count explicitly.
4. Audit log rows are cheap to lose individually but cumulative: avoid
   widening "just to be safe" when the actual harm is more deletion,
   not less.
