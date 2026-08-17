---
name: coresamples-v2-generate-sample-id-stale
description: coresamples v2 GenerateSampleID hands out ALREADY-USED sample ids (sequence ~311k behind lis_core_v7.sample) — never let its return value flow into an order; emr-v2 order path sends sampleId=0 and the portal order API self-assigns
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1881262d-c439-4bbc-924d-f47b78e742ae
---

Verified live 2026-07-02 (VP-17318): grpcurl to all 3 `coresamplesv2` AKS pods → GenerateSampleID returned 2277991–2278000, every one an EXISTING patient sample in `lis_core_v7.sample` (max was 2589806). The generator sequence is stale; a "fixed" client that reads the response correctly would inject colliding ids into orders.

Related facts:
- The proto field is `sampleId` (camelCase IN the .proto); emr-v2's client loads with `keepCase: true`, so the old `response.sample_id` read was always undefined → coerced to 0 — generateSampleID never worked in emr-v2, and that accidentally prevented collisions.
- POST `api.vibrant-wellness.com/v1/portal/order/orderTest/order` with `sampleId: 0` self-assigns a correct id (70/74 historical zero-id orders succeeded this way). Since VP-17318 the finalizer sends 0 explicitly and does not call the RPC.
- customerPay orders get their sample id from the charging API (transactionPay), which is why the breakage only hit patientPayLater orders.
- Re-enabling pre-generation requires coresamples v2 team to repair the sequence first ([[appserver04-ssh]] for on-prem emr-v2 pods; coresamples pods are in AKS ns `coresamplesv2`).
