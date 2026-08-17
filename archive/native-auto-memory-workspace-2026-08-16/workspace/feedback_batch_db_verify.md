---
name: feedback-batch-db-verify
description: "After batch DB INSERT/UPDATE, verify 100% of rows and every key column — never spot check"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f68836e5-4fed-4b28-bb93-f4ba73ec87d2
---

After running batch DB scripts (`insert-ehr-integration.ts`, `insert-order-client.ts`, multi-row UPDATE/INSERT), **verify every single row, every key column** before reporting success. Spot-checking a sample is not enough.

**Why:** VP-16175 (2026-04-17). Script inserted 7 Athena ehr_integrations rows. The **first row's `status` fell to Prisma `@default(PENDING)`** because the CLI flag was missing on the first invocation; rows 2-7 had the flag and went LIVE. I reported "7/7 全部正確" after spot-checking. Leo discovered the stuck PENDING row **33 days later** when the customer was still pending and called it "非常嚴重的錯誤". The verification — not the script bug — was the real failure.

**How to apply:**
- After any batch DB write, run a SELECT that includes **all rows from the ticket** and **all key columns** (status, integration_type, vendor_id, clinic_id, customer_id, NPI, created_at). Read every row.
- Watch for "first row vs rest" divergence: the first invocation may be missing a flag the user only added after seeing partial output. Don't assume rows look identical because the script ran the same loop.
- Standard verify template for `ehr_integrations` work:
  ```sql
  SELECT customer_id, status, integration_type, ehr_vendor_id, clinic_id, created_at
  FROM ehr_integrations
  WHERE customer_id IN (...full ticket list...) AND clinic_id = {practice_id}
  ORDER BY customer_id;
  ```
- "Reported success but customer still PENDING weeks later" is the failure mode to avoid. Better to spend 30 extra seconds reading every row than have Leo find a stuck row a month later.

Related: [[feedback_agent_workflow]] (confirm before executing), [[reference_azure_mysql]] (prod DB creds).
