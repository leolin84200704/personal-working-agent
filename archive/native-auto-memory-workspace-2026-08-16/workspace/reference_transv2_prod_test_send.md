---
name: reference_transv2_prod_test_send
description: How to do a controlled prod test-send of LIS-transformer-v2 emails from Mac (redirect all recipients to one address)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 46453069-1c8e-467f-808b-4357bc9bc19b
---

Pattern for "run a prod email job but send everything to hung.l only" in **LIS-transformer-v2** (used VP-17065 daily-report, 2026-07-01).

**Approach**: one-off `npx ts-node` script that instantiates the REAL service class directly (`new DailyReportService(...)`) — keeps production logic — with minimal real collaborators, and monkeypatches the email sink to force recipients. This does NOT boot the Nest app, so no ScheduleModule / other crons fire (avoids stray reminder emails via prod Kafka).

**The redirect guard (the key safety property)**: wrap `emailService.sendBuiltMessage(msg)` to overwrite `msg.To/Cc/Bcc = 'hung.l@zymebalanz.com'` before publishing. Guarantees no message reaches a real recipient regardless of what the service computed. Always run a `DRY_RUN` first (log `To(was=...)->hung.l` for every message) to confirm 100% redirect before the real send.

**Env facts (verified 2026-07-01)**:
- Local `.env` `DATABASE_URL_CALENDAR` points at the **dev** schema `calendar_dev_new` — NOT prod. Prod value is in ConfigMap `lis-transv2-config` (ns `transv2`): `postgresql://ehradmin:...@lis-postgresql.postgres.database.azure.com:5432/ehr-admin?schema=calendar_prod`. For prod data, set `process.env.DATABASE_URL_CALENDAR` to the prod URL at the TOP of the script (dotenv, run on `redis.ts` import, does NOT override an already-set var). datasource = `env("DATABASE_URL_CALENDAR")`, so `new PrismaClient()` then hits calendar_prod.
- `.env` `Azure_kafka_notification_url` / `_connection_string` == the prod ConfigMap values (`vibrant-notification-events.servicebus.windows.net:9093`, topic `notification-email-template`). So publishing from Mac = REAL prod delivery → Postmark → real inbox.
- Template id: `EmailTemplateConfigService.isStagingEnvironment()` = `NODE_ENV==='test' || SERVER_ENVIRONMENT==='stprod'`. Set `NODE_ENV=prod`, `SERVER_ENVIRONMENT=prod` → prod template ids. clinic 150105 reads `email-templates-clinician.yaml` (overrides default). Yaml resolved from `dist/` first then `src/` (postbuild copies it).
- Provider timezone gRPC (`TimezoneSettingService` → core `GetSettingByCustomerClinic`) uses an in-cluster addr in prod (`lis-core-grpc-service.default.svc.cluster.local:30113`) — UNREACHABLE from Mac. Stub `resolveProviderTimezone` → `'America/Los_Angeles'`; 150105 clinicians are all PST anyway (VP-17190), so output matches prod.
- Stub `ClinicSettingService.getColors` (cosmetic, avoids a gRPC call). Stub `ConfigService.get = (k,d)=>process.env[k]??d`. Stub logger.

**Cleanup**: the script embeds the prod DB password in plaintext — delete it after use, never commit. See [[project_vp17065_daily_report]] and [[reference_transv2_calendar_service]].
