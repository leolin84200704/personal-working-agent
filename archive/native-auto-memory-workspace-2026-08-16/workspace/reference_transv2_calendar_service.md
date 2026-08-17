---
name: transv2-calendar-service
description: LIS-transformer-v2 (calendar/getClinic) runs in AKS transv2 ns; gRPC stale-channel incident + debug method + v1/v2 core endpoints
metadata: 
  node_type: memory
  type: reference
  originSessionId: f53210c6-dfa9-4ea7-9046-008f1d295f83
---

**Service topology (verified 2026-06-16):**
- `LIS-transformer-v2` repo (calendar module: getClinic, clinic/patient/event/meeting-request, public booking) runs as **`lis-transv2-deployment` in AKS namespace `transv2`** (kubectl context `lisportalprod`), image `lis-transformerv2:<commit-sha>` (tag = git SHA). App listens :3390.
- **NOT** `lis-trans-deployment` in `default` ns — that's the OLD v1 trans (no `calendar/` module; its dist lacks it). Wasted hours probing the wrong one.
- Gateway `https://api.vibrant-america.com/v2/portal/trans-service[-st]/graphql` → transv2 (AKS).
- **appserver04 kubectl = on-prem cluster ONLY; cannot see transv2** (AKS). Need AKS `lisportalprod` context; pods are `-n transv2` (NOT default ns).
- ConfigMaps: `lis-transv2-config` (prod) / `lis-transv2-config-st` (staging) in transv2 ns.

**Core gRPC endpoints:** v1 = `CORE_RPC_STAGE` (lis-core-grpc-service.default.svc.cluster.local:30113, proto `protos/clinic.proto` pkg `lis`); v2 = `CORE_SAMPLE_V2_RPC` (lis-coresamples-v2-service.coresamplesv2.svc.cluster.local:8084, proto `protos2/coresamplev2/main.proto` pkg `coresamples_service`). **PREMISE (Leo): v1 data ≠ v2 data — do NOT switch a v1 read to v2 (or vice-versa); keep each read on its existing source.** `CORE_RPC_STAGE_CLOUD` is a **cloud-mirror of v1** (NOT v2 — code comment "cloud-mirror of v1Client, same proto/package as v1"); it was never set → NestJS gRPC url=undefined → dead `localhost:5000`. Calendar core reads (clinic/patient/setting/customer) have always been **v1**. So the **durable fix = read v1 (`CORE_RPC_STAGE`) directly, drop the dead `CORE_RPC_STAGE_CLOUD` cloud-primary + `withCloudFallback`** (PR #494) — NOT switch to v2. (I initially mis-fixed this by routing to v2; corrected.)

**getClinic "Database or server error" (INTERNAL_SERVER_ERROR) incident 2026-06-16:** intermittent ~2/3 failures were **per-pod** — pods up 2+ days had degraded long-lived gRPC channels (failed 100%); a recently-restarted pod worked 100%. Network + core service fine (fresh gRPC 40/40 OK). **Immediate fix = `kubectl rollout restart deploy/lis-transv2-deployment -n transv2`** (fixed: all new pods 15/15, gateway 12/12). Recurs over time until durable fix.

**Appointment confirmation email recipient (VP-17103):** the "to" for meeting-request/public-booking confirmation emails = `v2_calendar.calendar_owner_email` (OWN calendar Postgres, read via Prisma at send time — NOT the booker's entered email, NOT a re-query of proto). That column is a stale cache: written once at calendar creation from gRPC `GetPatient` (patient record), and `getOrCreatePatientCalendar` only **fills-if-missing** afterward (never overwrites). So an entered/changed email never reaches the recipient. **No exposed API updates an existing calendar's email** — `getOrCreateCalendar`/`createNewCalendar` don't even write `calendar_owner_email`; only public-booking `getOrCreatePatientCalendar` writes it (create + fill-if-null). To change it: manual SQL on `calendar_prod.v2_calendar`, or code. Setting writes (`CreateOrUpdateClinicSetting`/`EditCustomerClinicSettings`) are **core SettingService** gRPC (lis-core v1 `CORE_RPC_STAGE` / coresamples v2 `CORE_SAMPLE_V2_RPC`), not a calendar endpoint — calendar is just a client.

**Debug method (logger:false gotcha):** trans-service `main.ts` uses `NestFactory.create(...,{logger:false})` → Nest `Logger` suppressed, underlying errors NOT in pod logs; GraphQL resolver errors don't reach Sentry. So diagnose by: (1) per-pod reproduce — in-pod `node` minting a JWT from env (`JWT_SECRET_PROD||JWT_SECRET||(SERVER_ENVIRONMENT==='stprod'?secretOrKeyDev:secretOrKeyProd)`, HS256, payload `{user_id,customer_id,clinic_id,user_roles:[]}` with clinic_id matching) → POST `http://127.0.0.1:3390/graphql`; (2) direct gRPC via `@grpc/proto-loader` + `/protos/clinic.proto`. [[reference_appserver04_ssh]] [[reference_azure_mysql]]
