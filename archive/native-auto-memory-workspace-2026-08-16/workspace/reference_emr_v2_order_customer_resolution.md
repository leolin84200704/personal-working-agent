---
name: reference_emr_v2_order_customer_resolution
description: "emr-v2 HL7 order customer resolution = ehr_integrations winner (LIVE+ordering, typeRank then updated_at DESC), NOT order_clients; one NPI with 2 integrations → order resolves to wrong customer"
metadata: 
  node_type: memory
  type: reference
  originSessionId: f53210c6-dfa9-4ea7-9046-008f1d295f83
---

emr-v2 resolves an HL7 order's customer from the ORC.12 NPI via `CustomerDetailFetcherService.fetchByNpi` → gRPC `getCustomerByNPINumber` → `resolveOrderingIntegration` on **ehr_integrations** (WHERE status='LIVE' AND ordering_enabled=true), sorted by typeRank (FULL_INTEGRATION=0, ORDER_ONLY=1, else 2) then `updated_at` DESC, returns `candidates[0].customer_id`. `fetchById` also goes through `resolveOrderingIntegration`. **order_clients is NO LONGER consulted** (superseded ~VP-16968; processor comment confirms). This corrects an earlier belief that order resolution used order_clients.

Gotcha: if one NPI has **multiple** LIVE+ordering ehr_integrations, the most-recently-updated FULL one wins. A custom bundle (order-mapping-cache key `${oldOrderTypeId},${customerId}`) bound to a DIFFERENT customer than the winner → lookup miss → `emr_code_not_found`. Fix = align the bundle's customer, or deactivate the duplicate/stale integration so the NPI resolves to the intended customer. (2026-06-19: NPI 1396844346 had integrations on customer 3057 (newer) & 4953; bundles VACP149591/149592/126422 were on 4953 but orders resolved to 3057 → stuck; resolved by setting 3057→PENDING.)

Related: the stuck orders did not auto-recover because emr-v2 made parse failures terminal — see [[project_emr_backend_retired]] and VP-17120 (retry-rescan restore).
