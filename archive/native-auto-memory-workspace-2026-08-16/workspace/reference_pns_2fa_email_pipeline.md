---
name: pns-2fa-email-pipeline-debug-access
description: "How patient-portal (PNS) create-account/reset 2FA emails flow end-to-end, and how to debug delivery in prod"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 55961e92-ab11-4f17-9694-fcf3779c383a
---

Patient-portal (PNS / MyWellness) 2FA email flow, end-to-end (verified 2026-05-26 investigating hrwilliams50@gmail.com "收不到"):

Flow: patient-portal frontend → coresamples-v2 gRPC `PatientService.PatientSendCreateAccountEmail` (LIS-backend-v2-coreSamples/service/patient_service.go) → generates OTP, stores `code:email` in Redis (10min TTL) → HTTP `util.PnsSendCreateAccount2faAuthEmail` POST to `https://api.vibrant-wellness.com/v1/portal/trans-service/valogin/PnsSendCreateAccount2faAuthEmail` (deployed path is `trans-service`, NOT `trans-service-st` as in local repo — deployed code diverges) → trans-service `valogin.controller.ts` → `pnsSend2faCodeEmail` (valogin.service.ts) publishes Kafka topic `Notification-Email-Template` on `vibrant-notification-events` Event Hub → `noti/notification-center-deployment` consumer → Postmark.

Debug access (this machine, 2026-05-26):
- `kubectl` context `lisportalprod` works (prod). Pods: trans = `default/lis-trans-deployment-*` (env SERVER_ENVIRONMENT=prod) + `lis-trans-deployment-st` (stprod). coresamples = `coresamplesv2/lis-coresamples-v2-deployment-*`. consumer = `noti/notification-center-deployment-*`.
- `az` CLI logged in but MANAGEMENT plane needs MFA re-login (Log Analytics blocked until `az login`).
- Postmark: token hardcoded in trans `src/utility/utility.service.ts` = `e4e352ed-6abd-41a2-84eb-b3d0b01bbac1` → server **LIS (8340335)**. consumer (`noti/notification-center`) env `POSTMARK_KEY_ZYMEBALANZ` → server **ZymeBalanz (5595198)**.
- **PNS emails are split across TWO Postmark servers by type — search the right one or you'll see "找不到":**
  - PNS **2FA account create/reset** (templates 4059xxxx, Tag "PNS Two-Factor Authentication") → **ZymeBalanz (5595198)**.
  - PNS **kit lifecycle** notifications (Tag `consume_pns*` e.g. KitShippedBack/KitDelivered/KitLabReceived, templates 33xxxxxx) → **LIS (8340335)**.
- Query: `GET api.postmarkapp.com/messages/outbound?recipient=X&count=N&offset=0` (offset is REQUIRED, else ErrorCode 700). Then `/messages/outbound/{id}/details` for delivery events, `/dump` for raw MIME. Match by recipient+Tag+Metadata(sample_id/accession_id), NOT by the bus MessageID — the Kafka/EventHub message's `MessageID`/`partitionKey` is the producer id; Postmark assigns its OWN MessageID on send.
- To read the bus directly: topic `Notification-Email-Template` is a single-partition Event Hub on `vibrant-notification-events`; connection string (SendListen) in `LIS-transformer/.env` `Azure_kafka_connection_string`. Read safely via `@azure/event-hubs` EventHubConsumerClient ($Default, no checkpoint) — AMQP non-epoch read won't steal partitions from the live consumer (kafkajs consumer-group read WOULD rebalance/steal — avoid). Script kept at /tmp/ehread/read.js.

Gotchas:
- All app logs (trans `lis_front_logger`, coresamples zap) go to **stdout only** (no DB, no fluentd). Pull via `kubectl logs` or Log Analytics.
- trans `LoggingInterceptor` logs req+resp inside RxJS `tap` (AFTER handler completes) → a **hung/timed-out request leaves NO log at all** in trans.
- coresamples `PostJSON` has a **30s client timeout**; on timeout it deletes the Redis session and returns 500, **no email, no retry** → transient blips silently drop verification emails. Error: `context deadline exceeded (Client.Timeout exceeded while awaiting headers)`.
- trans `pnsSend2faCodeEmail` does `Promise.all([localKafka.connect(), azureKafka.connect()])` on EVERY request even when `platform_type=cloud` (which sends via azure) → a **local Kafka (`default/lis-core-kafka`) outage hangs cloud email sends** → 30s timeouts. Seen 2026-05-26 19:12–19:40 UTC (209 coresamples timeouts; lis-core-kafka pod replaced 19:30:19 UTC).
- Consumer (`notification_center` image, /app/src/notification/consumer.service.ts) dispatch by `job.data.TemplateId`: (1) `sendGrid[id]` set → SendGrid dynamic template; (2) `zymeb[id]` set → ZymeBalanz Postmark server with the REMAPPED id; (3) else → LIS server with original id. Separate raw-HTML `sendEmail` path only for jobs carrying HtmlBody/TextBody (2FA carries TemplateId+TemplateModel → template path, NOT raw HTML).
- The `zymeb` remap table (/app/src/notification/ZymeBalanz-server.ts) maps LIS template ids → ZymeBalanz ids, e.g. `40591105→41526507` (ZymeBalanz "...- staging"), `40591139→41526542` (ZymeBalanz "Account Creation Verification" = PROD). So the trans env-ternary (`stprod?40591105:40591139`) NETS OUT CORRECT once remapped: real prod (`SERVER_ENVIRONMENT=prod`) → 40591139 → ZymeBalanz **41526542 (prod)**; stprod → 40591105 → 41526507 (staging). The "...Staging"-named LIS id is NOT a bug — naming is cross-wired across servers but prod customers get the prod template. (Corrects an earlier wrong assumption that prod used a staging template / that 2FA was sent as raw HTML — it is a remapped TEMPLATE send. Postmark's message-detail endpoint returns TemplateId=null for template sends, which misled the raw-HTML guess; Metadata + rendered body confirm template send.)
