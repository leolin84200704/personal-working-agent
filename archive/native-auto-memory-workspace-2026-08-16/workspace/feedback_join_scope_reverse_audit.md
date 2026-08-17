---
name: join-scope-reverse-audit
description: prod UPDATE-WHERE-JOIN 跑完後，必須用更廣的 criterion 反向 SELECT 找漏網的 row。SQL 的 NULL=NULL=false 會 silently miss、ROW_COUNT 看起來正常但 scope 不完整。
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 904372bb-59eb-4895-ba9d-b023a08378ae
---

**Rule**：對 prod 跑 batch `UPDATE ... JOIN ... WHERE ...` 後，**不要只看 ROW_COUNT + 對 updated row 做 100% diff**（[[feedback_batch_db_verify]] 那層），還要**反向 audit scope**：

```sql
-- 例：原 UPDATE 用 (cust+clinic) OR NPI join
-- 反向：用更廣 criterion 找「應該在 scope 但 JOIN 漏掉」
SELECT COUNT(DISTINCT ei.id) AS missed
FROM ehr_integrations ei
WHERE (ei.integration_type <> 'FULL_INTEGRATION' OR ei.ordering_enabled = 0)
  AND EXISTS (SELECT 1 FROM order_clients oc WHERE oc.customer_id = ei.customer_id)
  AND NOT EXISTS (
    SELECT 1 FROM order_clients oc
    WHERE (oc.customer_id = ei.customer_id AND oc.clinic_id = ei.clinic_id)
       OR (oc.customer_provider_NPI = ei.customer_npi COLLATE utf8mb4_unicode_ci
           AND oc.customer_provider_NPI <> '')
  );
-- > 0 = 你的 JOIN 漏了這些 row、補 UPDATE
```

**Why**：SQL 標準 `NULL = NULL` 是 false。任何 JOIN 鍵欄位有 NULL 都會 silently 漏掉。INCIDENT-20260529 案例：customer 508387，oc.clinic_id=508387 / ei.clinic_id=19232（V1 用 customer_id 當 clinic_id placeholder、V2 升級成真實 clinic_id），customer_provider_NPI 跟 customer_npi 兩邊都 NULL → `(cust+clinic) OR NPI` 兩 branch 都 false → JOIN miss 整 row。Leo 直接點名 508387 才被抓出來、否則 silently 永久漏掉。

**How to apply**：
- 任何 prod `UPDATE/DELETE WHERE 有 JOIN 或 EXISTS` 之後必跑反向 audit
- JOIN 鍵裡有 nullable 欄位（NPI / clinic_id / customer_npi 等）特別高風險
- 漏網 count > 0 → 補 UPDATE 或檢討 JOIN 邏輯
- NULL-safe 操作符 `<=>` 可用、或顯式 `COALESCE`/`IS NULL` 處理；但反向 audit 還是要跑（cheap + 抓 logic bug 不只 NULL）

**跟 `[[feedback_batch_db_verify]]` 的關係**：
- batch-db-verify = 「我 update 了的 row 是否真的變對」(post-state correctness)
- 本 feedback = 「我 update 的 scope 是否完整」(scope coverage)
- 兩個都做才完整

關聯：[[INCIDENT-20260529]]、`lis-code-agent/long-term-memory/patterns.md` 「UPDATE-WHERE-JOIN scope 必反向 audit」。
