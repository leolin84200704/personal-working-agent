# LIS-transformer-v2 Calendar Module — AI Reference Doc

> **Purpose**: let an AI agent answer most questions about the trans-v2 calendar module WITHOUT re-reading the codebase.
> **Scope**: `/Users/hung.l/src/LIS-transformer-v2/src/calendar/` (plus app-level wiring it depends on).
> **Snapshot date**: 2026-07-28 (code on branch `stage_test` @ a453397; prod DB stats queried live same day).
> **Caveats**: `file:line` refs drift as code changes — treat them as anchors, re-grep the method name if a line doesn't match. DB row counts are a point-in-time snapshot. For "current state" questions (is X deployed? did Y change?), verify against ground truth (repo / prod DB / Jira) per RETRIEVAL.md.

---

## 1. TL;DR

- Calendar is the appointment/scheduling backend inside the **LIS-transformer-v2** service (NestJS 11, port 3390, GraphQL + REST). ~180 files / ~44k LOC under `src/calendar/`, 17 sub-modules wired via `src/calendar/calendar.module.ts` (imported at `src/app.module.ts:149`).
- Own datastore: **PostgreSQL** (Azure `lis-postgresql.postgres.database.azure.com`, db `ehr-admin`, schema `calendar_prod`) via **Prisma 6**. All LIS-core data (patient/clinic/customer/setting) is fetched over **gRPC**, never SQL.
- Async: **Kafka producer-only** (kafkajs; dual-publish Azure Event Hub + on-prem Kafka). **No Bull/BullMQ in this repo** — Bull reminder queues live only in legacy `LIS-transformer`. v2 reminders = 2-minute cron + Postgres idempotency table.
- Heaviest real-world use today: **Vibrant Clinical Team consults (practice_id 150105)** — Call / Zoom Meeting / Clinical Consult events, ~800–1,100 events/month. Public booking, meeting types, external calendar sync are live but early-adoption (see §12 usage stats).
- Consumers: clinic/provider portal ("VI My Calendar" / UniMod, GraphQL), patient portal (GraphQL), public patient booking site `{clinic}.mypatienthubs.com` (REST, unauthenticated), Google/Microsoft webhooks. Prod sits behind gateway prefix `api.vibrant-america.com/v2/portal/trans-service/` (staging `.../trans-service-st/`).

---

## 2. Service context

| Item | Value |
|---|---|
| Repo | `/Users/hung.l/src/LIS-transformer-v2` (GitHub `Vibrant-America/LIS-transformer-v2`) |
| Service name | `lis-transformer-v2` / Sentry tag `lis-trans-service-v2`; image `vibrant/lis-transformerv2` |
| Framework | NestJS 11, Apollo Server 4 (`@nestjs/graphql` 13, code-first `autoSchemaFile: true`) |
| Port | 3390; health `GET /health`; Swagger at `/api` |
| GraphQL hardening | introspection only when `platform_type === 'local'`; playground off; landing page off in prod (`src/app.module.ts:31-56`). PR #515 = compliance disable-introspection |
| CORS | `app.enableCors()` with NO options = all origins allowed (`src/main.ts:32`) |
| Deploy | AKS cluster `lisportalprod`, namespace `transv2`, Deployment `lis-transv2-deployment`, container `lis-transv2`, **replicas 3** (hence all the multi-pod dedup patterns). CI: push `main` → GH Actions `frontend-service-graphql.yml` → `az acr build` (ACR `lisportalprod`) → k8s-deploy with `yaml/prod.yml`. Staging: `stage_test` branch → `frontend-service-graphql-st.yml`, ConfigMap `lis-transv2-config-st` |
| Env injection | Almost all env from ConfigMap `lis-transv2-config`. NOTE: `DATABASE_URL_CALENDAR`, `Azure_kafka_*`, `ZOOM_*/GOOGLE_*/OUTLOOK_*` are NOT in `yaml/prod.yml` — supplied via another ConfigMap/Secret/App-Config not tracked in repo |
| Env-branching flags | `SERVER_ENVIRONMENT` (`prod`/`stprod`), `platform_type` (`local` gates crons/introspection/Redis mode), `NODE_ENV` (`test` ⇒ staging templates/topics), `aks_server_type` (`test` ⇒ password Azure Redis), `GRPC_CLOUD_FALLBACK_ENABLED`, `WEBHOOK_BASE_URL` |
| Dockerfile | node:20 → node:20-alpine, `npx prisma generate` both schemas, copies `protos`, `prisma`, `rsa-key`, `qpdf` installed, `CMD npm run start:prod` |

---

## 3. Module map (17 sub-modules under `src/calendar/models/`)

| Dir | One-liner | Main files (sizes at snapshot) |
|---|---|---|
| `event/` | Event CRUD + RRULE recurrence + side effects — THE core | `event.resolver.ts`, `event.service.ts` (5,985 lines), `event.model.ts` |
| `schedule/` | Weekly working hours + date exceptions | `schedule.service.ts` (923) |
| `calendar/` | `getOrCreateCalendar` bootstrap; role-based calendars | `calendar.service.ts` (573) |
| `public_booking/` | Unauthenticated patient self-booking REST | `public-booking.controller.ts`, `public-booking.service.ts` (1,199) |
| `meeting-request/` | Patient→provider request lifecycle + **availability engine** | `meeting-request.service.ts` (1,906), `provider-availability.service.ts` (1,114) |
| `calendar-sync/` | Google / Outlook / Zoom integration (OAuth, 2-way sync, webhooks) | `calendar-sync.resolver.ts` (1,111), `zoom.service.ts` (1,404), `outlook.service.ts` (1,211), `google.service.ts` (868) |
| `reminder/` | 48h/24h/15m appointment reminder cron (150105 only) | `reminder.service.ts` (310) |
| `notification/` | Email dispatch: YAML Postmark template registry → Kafka | `email.service.ts`, `email-template-config.service.ts` |
| `task/` | Tasks w/ recurrence; GraphQL Subscriptions + SSE | `task.service.ts` (973), `task-sse.controller.ts` |
| `daily-report/` | VP-17065 Mon–Fri xlsx report cron (150105) | `daily-report.service.ts` (505) |
| `accession-claim/` | VP-16410 one-event-per-accession lock (150105) | `accession-claim.service.ts` (282) |
| `meeting-type/` | VP-16512/16514 provider bookable meeting types (REST) | `meeting-type.service.ts` (289) |
| `clinic-location/` | Clinic physical locations CRUD | `clinic-location.service.ts` (348) |
| `clinic/` | Read model over core via gRPC + KPIs (declined rate, active patients) | `clinic.service.ts` (620) |
| `customer/` | Provider/customer read model via gRPC | `customer.service.ts` |
| `patient/` | Thin gRPC `getPatient` wrapper | `patient.service.ts` |
| `setting/` | User settings (timezone, booking rules, practice event types) + clinic branding | `user-settings.service.ts` (1,010) |
| `shared/` (models) | PrismaService, Kafka producers (AppointmentEvent/TaskEvent), TimezoneSettingService, JwtUtil | — |

Also: `src/calendar/shared/` (SharedModule global Prisma, enums, `with-cloud-fallback.util.ts`), `guard/` (AuthGuard/CalendarAuthGuard/RateLimitGuard), `decorators/`, `dto/`, `migration/` (one-off CLI scripts, NOT registered in AppModule, read legacy MySQL `crm` directly).

---

## 4. Feature deep-dives

### 4.1 Event lifecycle (`models/event/`)

`v2_event` has **NO status enum — only `is_canceled` boolean** drives open/pending reporting. Recurring model: master row holds `rrule` (+ `recurrence_end_time`); per-occurrence changes go to `v2_event_exception` (unique `(master_event_id, recurrence_id)`); reads expand via `expandRecurringEvent` (`event.service.ts:3916`).

**Create** — `EventService.createEvent` (`event.service.ts:465`):
1. `validateEventCreationPermission` → `validateEventParticipants` → `resolvePracticeEventTypeForCreate`
2. `validateRecurringSeriesConfig`: RRULE parse, `DTSTART` must equal `start_time`, computes `recurrence_end_time`
3. practice 150105 + `accession_ids`: `prisma.$transaction` wrapping `v2_event.create` + `AccessionClaimService.claimForEvent` — unique violation on `accession_id` rolls back the event (VP-16410 anti-double-book)
4. `v2_event_participant.createMany` (explicit `participants[]`, else derived from `customer_id`/`patient_id`)
5. Fire-and-forget side effects: email (template registry), Kafka `event-created`, Zoom meeting create for video types, `syncEventToExternalServicesOnCreate`

**Update** — `updateEvent` (`:704`): `resolveRecurringEditScope` (`:3552`) then one of:
- whole event: `buildWholeEventUpdateData` (`:3580`)
- `THIS_EVENT`: upsert `v2_event_exception` row
- `THIS_AND_FUTURE`: `buildTrimmedRecurringRule` + create new future series (`:3719-3751`)
Accession delta handled by `syncForEventUpdate`.

**Delete/cancel** — `deleteEvent` (`:948`): scope-aware (THIS_EVENT ⇒ cancelled exception; THIS_AND_FUTURE ⇒ trim `recurrence_end_time`; ALL_EVENTS ⇒ cancel series). Releases accession claims; propagates to Google/Outlook/Zoom.

**Reschedule (Clinical Consult, 150105 only)** — `rescheduleClinicalConsult` (`:4882`) + `fireRescheduleSideEffects` (`:5040`), from VP-16520/16521:
- same clinician ⇒ in-place update (email `appointment_updated`, Kafka UPDATED)
- different clinician ⇒ **cancel-and-rebook**: original event `is_canceled=true`, new event on new clinician's calendar copying `creator_calendar_id`/`practice_event_type`/`accession_ids`; same transaction releases→claims accessions (avoids VP-16410 1:1 collision). Kafka fires CANCELLED + CREATED pair (`:5025-5028`); emails = cancel(old) + create(new) + update(provider)

**Patient-facing variants** (150105 provider-as-patient flows): `createEventByPatient` (`:1549`), `updateEventByPatient` (`:1895`), `deleteEventByPatient` (`:2078`). Participation/RSVP: `updateMyEventStatus` (`:1283`), per-occurrence via `v2_event_participant_exception`.

**Reads**: `getEvents` (`:178`, recurrence-expanding), `getCancelledEvents` (`:308`, merges cancelled masters + cancelled instances), `getEventByEventId`, `getNextAvailableTime` (`:430`).

### 4.2 Availability (two engines)

1. **Event-side**: `getNextAvailableTime` → `generateScheduleAwareSlots` (`:2485`) → `filterAvailableSlots` (`:2579`) with `hasEventConflict`/`areAllCalendarsAvailable`/`checkMultipleExceptionsAvailability`/`checkRegularScheduleAvailability`/`mergeTimeWindows` (`:2603-2718`). **Fallback when no `v2_schedule` rows: Mon–Fri 09:00–17:00** (documented in `models/event/README.md`).
2. **`ProviderAvailabilityService`** (`models/meeting-request/provider-availability.service.ts`) — shared by meeting requests AND public booking: `getProviderAvailability` (`:148`), `getRescheduleAvailability` (`:245`), `validateSlotAvailability` (`:366`, VP-16850 — public booking rejects out-of-availability slots). Pipeline: working schedule → schedule exceptions → existing events → **pending meeting requests also block slots** → `calculateAvailableSlots`/`calculateSlotsWithExceptions` → `mergePeriods` → `generateSlotsFromPeriods`. Also `createPatientCalendarForCustomerIfAbsent` (`:614`).

### 4.3 Public booking (`models/public_booking/`, REST `/api/booking`)

Unauthenticated; only `RateLimitGuard` (Redis INCR + expire). Flow:
`GET /practices/:id/doctors` → `GET /appointment-types` → `GET /availability/:providerId/:practiceId` → `POST /verification-code/send` + `/verify` (code in Redis `transv2::public_booking::verification_code::<email>`, setex) → `POST /patient/lookup` or `POST /patients` (gRPC `PatientService.CreatePatientV2`) → `POST /appointments/request` → `DELETE /appointments/:id/cancel`.

`createAppointmentRequest` (`public-booking.service.ts:537`): resolve patient + provider calendars (auto-create patient calendar if absent) → `validateSlotAvailability` → `resolvePracticeEventType` → `v2_meeting_request.create({status:'pending'})` → `sendMeetingRequestEmails`. Booking URL: `https://{sanitized-clinic-name}.mypatienthubs.com/booking/{providerId}` (`BASE_DOMAIN='mypatienthubs.com'` at `:192`); persists `pns_subdomain` clinic setting via gRPC. Google sign-in variant via `google-userinfo.service.ts`. Verification email goes out via **on-prem** Kafka topic `'Notification-Email-Template'` (see §8 casing gotcha).

Rate limits: patients 5/60s, appointment request+cancel 10/60s, verification send 3/300s, verify 5/60s, lookup 20/60s, doctors/types/timezones 30/60s, logo 50/60s. Note: `openapi.yml` documents `GET /csrf-token` that has NO controller route.

### 4.4 Meeting requests (`models/meeting-request/`)

Lifecycle: pending → accepted / rejected / canceled. Patient side: `createMeetingRequest` (`:194`), `updateMyMeetingRequest` (`:390`), `cancelMyMeetingRequest` (`:459`). Provider side: `updateMeetingRequestForMe` (`:1112` — accept/reject/reschedule). On accept: `checkMeetingConflict` (`:1601`, includes RRULE conflict expansion `:1007/:1052`) → `createEventFromMeetingRequest` (`:1529`) → backfills `accepted_meeting_id` (FK to `v2_event.uuid`) → emails + Kafka (`meeting-request-*` + an extra `event-created`). Cancel cascades via `cancelAssociatedEvent` (`:1093`).

### 4.5 External calendar sync (`models/calendar-sync/`)

- **Outbound orchestration** — `calendar-sync.service.ts`: `syncEventToExternalServicesOnCreate` (`:225`) / `...OnUpdate` (`:280`) / `syncRecurringInstanceUpdateToExternalServices` (`:334`) / `syncRecurringInstanceCancelToExternalServices` (`:391`) / `syncRecurringSeriesTruncationToExternalServices` (`:434`) / `deleteEventFromExternalServices` (`:485`) / `backfillEventsToGoogle` (`:53`). Per-attendee integration lookup (`findIntegrationsForAttendees:118`), `retryWithBackoff` 3 attempts. Called from ~13 sites in `event.service.ts`.
- **Google**: `google-oauth.service.ts` (scopes userinfo.profile + calendar; googleapis 149); `google.service.ts` (calendar_v3 CRUD, `syncGoogleCalendarBusySlots:614`, recurring-instance ops); `google-inbound-sync.service.ts` (watch channels: `registerWatchChannel:30`, `renewExpiredChannels:97`, `processWebhookNotification:126`, `fetchAndUpsertChanges:177`, `upsertGoogleEvent:269`, `doFullSync:345`).
- **Outlook / MS Graph**: `outlook-oauth.service.ts` (token endpoint login.microsoftonline.com/common, validates via `GET graph/v1.0/me/calendar`); `outlook.service.ts` (Graph CRUD, RRULE↔Graph recurrence converters `:869/:934`); `outlook-inbound-sync.service.ts` (subscriptions `:43`, `renewExpiredSubscriptions:115`, webhook processing `:163`, `pollAllConnectedOutlook:204` fallback).
- **Zoom**: `zoom.service.ts` — OAuth (`generateAuthUrl:179`, `exchangeCodeForTokens:199`, `refreshToken:521`), meetings (`createZoomMeeting:760` = `POST api.zoom.us/v2/users/me/meetings`, `updateZoomMeeting:851`, `deleteZoomMeeting:916`, `createStandaloneZoomMeeting:616`, `generateLinkForProvider:1255`), recordings (`listMeetingRecordings:1083`, `getAuthenticatedDownloadUrl:1224`). Tokens on `v2_calendar.zoom_calendar_ids` (`:1016-1036`). `zoom-event.service.ts` glues event lifecycle → Zoom (`handleEventCreated:25` … `cleanupOrphanedZoomMeetings:293` — exists but NOT scheduled). JWT secret pick: `SERVER_ENVIRONMENT==='stprod' ? secretOrKeyDev : secretOrKeyProd` (`:985`).
- **Webhooks** — `calendar-webhook.controller.ts`, base `/calendar/webhooks`: `POST /google` (reads `x-goog-channel-id/-token/-resource-state`, ACK 200 then async, token verified in service); `POST /outlook` (echoes `validationToken` after rejecting `[<>"'&]`, ACK 202 then async). Public webhook base: `WEBHOOK_BASE_URL` env, else hardcoded `https://api.vibrant-america.com/v2/portal/trans-service{,-st}/calendar/webhooks` (`google-inbound-sync.service.ts:35-36`, `outlook-inbound-sync.service.ts:48-49`).
- **Token security**: OAuth tokens AES-encrypted via `encryption.service.ts`, stored in `v2_third_party_integration` (unique `(practice_id, calendar_owner_id, service)`, service ∈ google|outlook|zoom CHECK).
- **iCal**: `ical-generator` is in package.json but **never imported** in src/calendar — no iCal feature.

### 4.6 Reminders (`models/reminder/`) — NOT a queue

`@Cron('*/2 * * * *')` `runReminders` (`reminder.service.ts:101`; skipped when `platform_type==='local'`). Types from `reminder.constants.ts`: `reminder_48h`/`reminder_24h`/`reminder_15m` with maxStaleMs 60min/60min/5min. Candidate query: `v2_event` where `practice_id=150105`, `is_canceled=false`, `start_time ∈ [now+Δ−maxStale, now+Δ]` (`:122-135`).

**Multi-pod idempotency**: atomic claim = insert into `v2_reminder_audit_log` with UNIQUE `idempotency_key` = `reminder:{event_id}:{48h|24h|15m}:{epoch}:{calendar_id}`; Prisma `P2002` ⇒ another pod owns it (`:245-273`). Status `queued → sent|failed` + `attempt_count`. Recipients = participants with email, **excluding practice-150105 clinicadmin** (VP-16612). Per-recipient timezone via gRPC core `SettingService` (fallback PST). Delivery via `EmailService.sendBuiltMessage` → Azure Kafka → Postmark; clinician template `appointment_reminder` prod `33802989` / staging `39039016`.

### 4.7 Daily report (`models/daily-report/`, VP-17065)

`@Cron('1 0 * * 1-5')` TZ America/Los_Angeles (`daily-report.service.ts:72`); prod-only (returns on local/staging). Redis lock `SET daily_appointments_report:<date> 1 EX 90000 NX` (`:484-505`; lock intentionally retained if failure happened after the send phase). Builds per-clinical-team-member .xlsx (ExcelJS + RRule expansion) of the day's appointments — 20 fixed columns (19 legacy + `External_url`, PR #531). Emails each member + ops heartbeat to `REPORT_OPS_EMAIL='hung.l@zymebalanz.com'`; failure alert email. Purpose: outage backup for "VI My Calendar / UniMod" frontends. Template `daily_appointments_report` prod `45401442`, staging `0` (prod-only). Audit table `daily_report_run`.

### 4.8 Tasks (`models/task/`)

CRUD + RRULE recurrence (`v2_task` + `v2_task_exception` per-occurrence overrides), complete/uncomplete, paginated & category-grouped queries (`getTasksPaginated:703`, `getOrganizedTasks:748`, `expandRecurringTasks:802`). Real-time: 4 GraphQL Subscriptions (`task.resolver.ts:504-566`) AND SSE `GET /task-events` (30s heartbeat, `task-sse.controller.ts`), both fed by Redis PubSub (`task-pubsub.service.ts`, channels like `TASK_CREATED_<clinicId>`; ioredis duplicated clients + AAD token refresh). Kafka task events via `TaskEventService` (same topics as appointments). API doc: `models/task/doc/task-api.md`.

### 4.9 Accession claim (`models/accession-claim/`, VP-16410)

Enforces one-event-per-`accession_id` for practice 150105. `v2_event_accession_claim` (UNIQUE `accession_id`) + `v2_event_accession_audit_log` (actions: claimed / released_by_reset / released_by_event / backfilled / rejected). Ops: claim/release/sync-on-update/reset (`resetEventAccession` mutation), `isAccessionClaimable` query. Claims made inside the event-create transaction.

### 4.10 Smaller modules

- **schedule/**: `v2_schedule` weekly rows (calendar_id, weekday, time range) + `v2_schedule_exception` date-specific; overlap validation in transactions; batch exception writes. PK is legacy-named `v2_work_schedule_pkey`.
- **calendar/**: `getOrCreateCalendar` — prerequisite bootstrap for everything; role-based creation (provider/clinicadmin/patient), practice-scoped access validation, seeds default practice event types (hence `v2_practice_event_type` bloat, §5).
- **meeting-type/**: REST-only provider bookable meeting types: CRUD/soft-delete/reorder/toggle, slug + booking-URL generation, weekly + date-specific availability rows. Prod tables still empty (unused as of snapshot).
- **setting/**: `UserSettingsService` — settings live as COLUMNS ON `v2_calendar` (timezone, default_calendar_view, booking rules min_notice_minutes/max_advance_days/default_appointment_duration, working_hours_display), NOT in `v2_user_settings` (dead table). Practice event type CRUD (writes `v2_practice_event_type.color_hex` — the `v2_event_type_color_override` comment at `user-settings.service.ts:527` is STALE). `ClinicSettingService` = cached gRPC clinic brand colors. `TimezoneSettingService` (models/shared) is the timezone source of truth per VP-17190.
- **clinic/customer/patient/**: gRPC read models. `clinic.service.ts` also computes KPIs from calendar DB (`getDeclinedRate`, `getActivePatients`, `no_show_rate` resolve-field). `scheduler_calendar` resolve-fields return hardcoded `[]` (legacy placeholder).

---

## 5. Database — calendar PostgreSQL

**Connection**: `DATABASE_URL_CALENDAR` = `postgresql://ehradmin:***@lis-postgresql.postgres.database.azure.com:5432/ehr-admin?schema=calendar_prod`. Schema selection is **purely the `?schema=` query param** (Prisma sets search_path from it) — no runtime SET search_path in code. Schemas: `calendar_prod` (prod), `calendar_dev_new` (dev/staging analogue — there is NO `calendar_staging`). `CALENDAR_DATABASE_NAME` env is vestigial (referenced nowhere in src/).

**ORM**: Prisma 6 (`prisma/schema.prisma`), default client, global `PrismaService` (`models/shared/prisma.service.ts`). Model name == table name (no @@map). Migrations = **manual SQL** (`prisma/manual-migrations/`, `scripts/vp-*-apply-migration.js`), NOT `prisma migrate`.

**Agent-side access**: `/opt/homebrew/opt/libpq/bin/psql "$DATABASE_URL_CALENDAR-minus-schema-param"` then `SET search_path = calendar_prod`. Creds in `LIS-transformer-v2/.env`.

### 5.1 Active tables (with prod row counts @ 2026-07-28)

| Table | Rows | Key columns / constraints | Used by |
|---|---|---|---|
| `v2_calendar` | 48,800 | PK `calendar_id`; `uuid`; UNIQUE `(practice_id, calendar_owner_id)`; `role` enum role_type (clinicadmin/provider/patient); `calendar_owner_{id,firstname,lastname,email}`; `timezone` (default America/Los_Angeles); `is_active`; settings cols: `default_calendar_view`, `email_notifications`, `max_advance_days` (30), `min_notice_minutes` (2880), `working_hours_display`, `default_appointment_duration` (30), `specialties[]`; `google/outlook/zoom_calendar_ids[]` | everything (155 call sites) |
| `v2_event` | 6,899 | PK `event_id`; `uuid` UNIQUE; `creator_calendar_id` FK→v2_calendar; `practice_id`; `practice_event_type_id` FK; `event_type` varchar; **`is_canceled` bool (no status enum)**; `start_time`/`end_time` timestamptz; `timezone`; `rrule`; `recurrence_id`; `recurrence_end_time`; `patient_id`; `location`; `accession_ids text[]`; `google_event_id`/`outlook_event_id`/`zoom_event_id`; `external_url`; indexes on creator_calendar_id, event_type, practice_event_type_id, (practice_id,start,end) | event, reminder, daily-report, sync, KPIs (100) |
| `v2_event_participant` | 10,304 | `event_id` FK CASCADE, `participant_calendar_id` FK, `role`, `status` (confirmation_status) | event, reminder, no-show rate (26) |
| `v2_practice_event_type` | 71,584 | `practice_id`+`name(30)` UNIQUE, `color_hex(7)`, `is_canceled` — bulk from per-calendar default seeding | settings, event, meeting-request, public booking (72) |
| `v2_event_accession_audit_log` | 4,382 | accession action audit (enum v2_event_accession_action) | accession-claim |
| `v2_reminder_audit_log` | 3,756 | `idempotency_key` UNIQUE; `reminder_type`; `status` (reminder_audit_status); `attempt_count`; `scheduled_for`/`sent_at`; event_id FK CASCADE | reminder (23) |
| `v2_event_accession_claim` | 3,181 | **`accession_id` UNIQUE**, event_id FK CASCADE, claimed_at/by | accession-claim, event (9) |
| `v2_schedule_exception` | 188 | UNIQUE (calendar_id,date,start_time,end_time), `is_available` | schedule, availability (15) |
| `v2_schedule` | 129 | calendar_id FK, weekday, start/end time | schedule, availability (11) |
| `v2_task` | 121 | PK task_id, uuid, calendar_id, practice_id, created_by, priority, is_completed, rrule, category (task_category) | task (18) |
| `v2_task_exception` | 67 | UNIQUE (task_id, occurrence_date), action, override_* | task |
| `v2_third_party_integration` | 44 | UNIQUE (practice_id, calendar_owner_id, service); service CHECK google|outlook|zoom; encrypted access/refresh tokens; `extra_json` = watch-channel/subscription metadata; `expires_at` | calendar-sync (38) |
| `daily_report_run` | 8 | daily report audit | daily-report |
| `v2_event_exception` | 0* | UNIQUE (master_event_id, recurrence_id); override cols + is_canceled | recurring edits |
| `v2_event_participant_exception` | 0* | UNIQUE triple (master,recurrence,participant) | per-occurrence RSVP |
| `v2_meeting_request` | 0 | uuid; patient/provider_calendar_id FKs CASCADE; requested_start/end; status(50); `accepted_meeting_id` FK→v2_event.uuid SET NULL; cancellation_reason | meeting-request, public booking (34) |
| `v2_meeting_type` (+`_weekly_availability`, `_date_specific_hour`) | 0 | UNIQUE (provider_id, slug); duration/buffer/video conf/display_order/soft-delete | meeting-type |
| `v2_clinic_location` | 0 | clinic_id, address fields, is_active | clinic-location |

\* zero rows at snapshot = feature live but not yet exercised in prod (or data cleaned).

DB enums: `role_type`, `confirmation_status`, `task_category`, `reminder_type`, `reminder_audit_status`, `v2_event_accession_action`, `event_status`, `external_service`, `notification_method`, `notification_type`, `connection_status`, plus legacy (`gender`, `questionnaire_type`, `two_fa_type`).

### 5.2 Dead / legacy tables (in schema.prisma, NOT touched by runtime code)

`scheduler_event` (452), `scheduler_calendar` (136), `scheduler_calendar_event_relation` (454), `scheduler_event_resource`, `clinic_practice_eventcategory` (268), `event_notification` (1,186), `email_send_out_request`, `sms_send_out_request`, `system_notification`, `appointment_survey_request`, `questionnaire`, `user` (44), `user_external_service` (9), `v2_event_type` (6), `v2_event_type_color_override` (4), `v2_user_settings` (1), `v2_clinic_settings`, `v2_schedule_template`.
Notes: `user`/`user_external_service` appear only in a spec + as in-memory type shapes; `scheduler_calendar` only as a GraphQL field returning `[]`; `v2_user_settings` superseded by columns on `v2_calendar`; `v2_event_type` superseded by `v2_practice_event_type`.

### 5.3 Other datastores touched

- **MySQL** `lis_frontend_service` (prisma2 client): NOT used by calendar module at all.
- **MySQL `crm` @ 192.168.60.4:3307**: read directly only by one-off `migration/` scripts (clinician timezone backfill; legacy v1 `calendar` table) — never in request path.
- **gRPC to LIS core** (all wrapped in `withCloudFallback`, VP-16685 — cloud primary, on-prem fallback on transient codes, kill switch `GRPC_CLOUD_FALLBACK_ENABLED=false`): `PatientService` (GetPatient, CreatePatientV2, SearchPatientEmail), `ClinicService`, `CustomerService`, `SettingService` (GetSettingByCustomerClinic, GetClinicSetting, CreateOrUpdateClinicSetting, GetClinicIDbySettingResult), `auditlog.RecordAuditLog`. Metadata carries `{token, request_id, internal_user_id}` via `@RequestContext()`.
- **Redis**: rate-limit counters, public-booking verification codes, task PubSub, daily-report lock. NEVER a job queue in this repo.

---

## 6. API surface

### 6.1 GraphQL (10 resolvers — ALL require auth; no public GraphQL ops)

| Resolver | Queries | Mutations |
|---|---|---|
| Event | getEvents, getNextAvailableTime, getEventByEventId, getCancelledEvents | createEvent, updateEvent, deleteEvent, updateMyEventStatus, createEventByPatient, updateEventByPatient, deleteEventByPatient, rescheduleClinicalConsult |
| MeetingRequest | getMyMeetingRequests, getMeetingRequestsForMe, getMeetingRequest, getClinicMeetingRequests, getCanceledMeetingRequests, getProviderAvailability, getLabClinicianAvailability, getRescheduleAvailability | createMeetingRequest, updateMyMeetingRequest, cancelMyMeetingRequest, updateMeetingRequestForMe |
| CalendarSync (~30 ops) | get_calendar_info, get_google_auth_link, get_zoom_auth_link, get_provider_availability, get_google_login_info, google_sign_out, get_oauth_connection_status, isOutlookConnected, check_zoom_token_status, list_meeting_recordings, list_user_recordings, get_authenticated_download_url, subscribe_service | save_oauth_token, sync_event_to_outlook, exchange_outlook_code, refresh_outlook_token, sync/remove google & outlook busy slots, create/remove zoom meeting for event, disconnect_oauth, cancel_zoom_meeting, refresh_zoom_token, createZoomMeetingWithoutEvent, generateZoomLinkForProvider, linkZoomMeetingUrlToEvent |
| Schedule | getCustomerSchedule, getClinicSchedules | updateWorkingHours, add/update/delete ScheduleException, addBatchScheduleExceptions |
| Calendar | getCalendar, getCalendarsByPractice | getOrCreateCalendar |
| UserSettings | getUserTimezone, getUserSettings, getUserBookingRules, validateBookingTime, getAvailableTimezones, getAllEventTypes, getPracticeEventTypes | updateUserTimezone, updateUserBookingRules, updateEventTypeColor, deleteEventTypeColorOverride, create/update/delete PracticeEventType, replaceAllFutureEventType |
| Task | tasks, task, organizedTasks, tasksByCategory, allTasks, tasksByCreator, tasksByClinic, tasksByProvider + **4 Subscriptions** | createTask, updateTask, deleteTask, completeTask, unCompleteTask |
| Clinic | getClinic, getDeclinedRate, getActivePatients (+ resolve-fields clinic_customers, clinic_patients, event_category, locations, no_show_rate) | — |
| ClinicLocation | getClinicLocations, getClinicLocationById | create/update/delete ClinicLocation |
| Customer | getCustomer, listAdminCustomer (+ scheduler_calendar resolve-field → `[]`) | — |
| AccessionClaim | getClaimedAccessionIds, isAccessionClaimable | resetEventAccession |

### 6.2 REST controllers

| Controller | Base | Auth |
|---|---|---|
| PublicBookingController | `/api/booking` | NONE (RateLimitGuard only) — 15 routes, see §4.3 |
| CalendarWebhookController | `/calendar/webhooks/{google,outlook}` | NONE (channel-token / validationToken verification) |
| MeetingType(Provider)Controller | `/api/providers/:providerId/meeting-types`, `/api/meeting-types/...` | AuthGuard |
| TaskSseController | `GET /task-events` (SSE) | AuthGuard, clinic users |

17 unauthenticated endpoints total (15 booking + 2 webhooks).

---

## 7. Auth & user types (`guard/auth.guard.ts`)

Dual-payload JWT, dual algorithm: HS256 legacy shared secret (`secretOrKeyProd`/`secretOrKeyDev`) + RS256 OAuth2 via `process.cwd()/rsa-key` (VP-16547/16558; `:346-369`). 5-min-swept in-memory token cache. Helpers `getClinicId/getCustomerId/getUserId/isAdminUser/isClinicalTeamUser` (`:611-661`).

| Role | Detection | Capabilities |
|---|---|---|
| clinicadmin | clinic payload + admin/clinic_admin/clinic in user_roles | any calendar in clinic; clinic-wide reads; clinic-location writes |
| provider | clinic payload, non-admin | own calendar/settings/OAuth/meeting-types only |
| patient | `barcode` present, or role='patient', or patient_id w/o clinic fields | meeting requests + updateMyEventStatus; **403 on createEvent/updateEvent/deleteEvent** |
| clinicalteam | internal_user_role/role = 'clinicalteam' | cross-clinic (exempt from clinic_id requirement, `:493`); 150105 flows |
| anonymous | no token | `/api/booking` REST only |
| Google/Microsoft | webhook headers | `/calendar/webhooks/*` |

---

## 8. Async infrastructure

### Kafka — producer-only (kafkajs 2.2.4 direct; no @nestjs/microservices, no consumers in repo)

**Clients**:
- On-prem: `models/shared/kafka/kafka.service.ts` — clientId `mykafka_client`, brokers `KAFKA_BROKER_carlos1/2` (192.168.60.9:9095, 192.168.60.10:9095); throws if carlos1 missing.
- Azure Event Hub (Kafka protocol, SASL plain, user `$ConnectionString`): `src/shared/kafka/kafka-appointment-event.client.ts` (`Azure_kafka_general_events` = general-events.servicebus.windows.net:9093), `kafka-azure-notification.client.ts` (`Azure_kafka_notification_url` = vibrant-notification-events.servicebus.windows.net:9093).

**Producers & topics**:

| Producer | Topic(s) | Trigger | Notes |
|---|---|---|---|
| `AppointmentEventService` (`models/shared/appointment-event/`) | Azure `general-sample-events`(+`-staging`) AND on-prem `lis-general-events` (staging_ prefix) — dual publish Promise.all, each failure caught; success = either sent | event CREATED/UPDATED/CANCELLED/DELETED (~13 sites in event.service); meeting-request lifecycle; reschedule fires CANCELLED+CREATED pair | payload: event_provider `ehr-calendar`, event_name `event-created`/`event-updated`/`event-canceled`/`event-deleted`/`meeting-request-*`, plus customer/clinic/patient/accession/order/sample ids, addon_column w/ participants. Downstream = LIS activity-timeline "calendar card" pipeline |
| `TaskEventService` | same two topics | task CRUD | event_types TASK_CREATED/UPDATED/COMPLETED/DELETED |
| `EmailService` (`models/notification/email.service.ts`) | Azure `notification-email-template` (env `Azure_notification_topic`) | all appointment emails, reminders, daily report | Postmark-shaped envelope (MessageID, Tag, From `Vibrant <notification@vibrant-america.com>`, TemplateId, TemplateModel, Delay, MessageStream outbound, Attachments). Downstream = notification service → Postmark. Legacy path has hardcoded templates 38719290 (patient) / 38777577 (provider); modern path = `sendBuiltMessage` from YAML registry. Errors swallowed unless throwOnError |
| `AppointmentNotificationEmailService` (`models/shared/appointment-notification-email/`) | **on-prem** Kafka, topic `'Notification-Email-Template'` (**different casing** from Azure `notification-email-template`!) | ONLY public-booking verification-code email | uses on-prem KafkaService, not Azure |

Staging detection for topics/templates: `NODE_ENV==='test' || SERVER_ENVIRONMENT==='stprod'`.

### Bull / BullMQ — NOT HERE

- v2 repo: no bull/bullmq/@nestjs/bull anywhere.
- Legacy `LIS-transformer` repo: `src/calendar/email/` has Bull queues `reminder_24h/48h/15m` (delayed jobs, jobId=event.id, attempts 5, backoff 5000, Postmark template 33802989, for v1 `calendar` table events), consumed by `lis-trans-deployment-st` pod (SERVER_ENVIRONMENT=stprod) — sends REAL prod email (VP-17421). Redis selection there: stprod|mac ⇒ on-prem `REDIS_ADDR/REDIS_PORT`, else Azure. Legacy .env shows 192.168.62.79:4647 (older memory said 192.168.60.9:4646 — .env now differs; k8s ConfigMap injects actual values).

### Cron (all 4 in calendar; `@nestjs/schedule` 6, registered in calendar.module.ts:22)

| Schedule | Job |
|---|---|
| `*/2 * * * *` | ReminderService.runReminders (§4.6) |
| `0 1 * * *` PT | InboundSyncScheduler.fallbackPollOutlook |
| `0 1 * * *` PT | InboundSyncScheduler.renewOutlookSubscriptions |
| `1 0 * * 1-5` PT | DailyReportService.runDailyReport (§4.7) |

### Redis (`src/redis.ts`)

Three connection branches: (1) `aks_server_type==='test'` ⇒ `Azure_redis_host/port/pass` TLS; (2) other cloud ⇒ Azure Redis discovered from **Azure App Configuration** (`appConfigRedisKey='endpoint:cloud-redis'`) with **managed-identity AAD token** as password (scope https://redis.azure.com/.default), proactive refresh 5 min before expiry — requires workload identity `transv2-identity-provider`; (3) local ⇒ `REDIS_ADDR/REDIS_PORT` (repo .env: 192.168.62.79:4647). Uses: locks, verification codes, rate limiting, RedisPubSub (graphql-redis-subscriptions) for task subscriptions/SSE.

---

## 9. Email / Postmark template registry

- Registry: `models/notification/email-template-config.service.ts` loads `email-templates.yaml` + `email-templates-clinician.yaml` (js-yaml; dist path first, src fallback; postbuild copies YAMLs to dist/).
- `getTemplateId(notificationType, recipientType, clinicId)` picks prod vs staging id. **Clinic 150105 swaps in the entire clinician YAML** (`CLINICIAN_CLINIC_ID`).
- Known ids: appointment_scheduled_by_provider patient 41893866/41930198(stg); appointment_canceled patient 41918287; clinician appointment_reminder 33802989/39039016(stg); clinician daily_appointments_report 45401442/0.
- Notification types fired from event.service: appointment_scheduled_by_provider (:4434), appointment_scheduled_by_patient (:4611), appointment_updated_by_patient (:4789), appointment_canceled_by_patient (:5335), appointment_canceled (:5483), appointment_updated (:5695), appointment_confirmed_by_patient (:5854); meeting_request_created (meeting-request.service :316/:358).
- Staging Postmark templates wrap body in `{{# English}}…{{/ English}}` ⇒ staging code nests template model under `English` (reminder.service.ts:334).
- **No SMS** in calendar (twilio exists elsewhere in repo; `notification.service.ts:61-63` early-returns for non-email methods).

---

## 10. Frontends / callers

| Caller | Protocol | Evidence |
|---|---|---|
| Clinic/Provider portal "VI My Calendar" / UniMod | GraphQL | guard/README.md; daily-report constants name them |
| Patient portal | GraphQL | PatientPayload.barcode; *ByPatient/My* naming |
| Public booking site `{clinic}.mypatienthubs.com` | REST | BASE_DOMAIN in public-booking.service.ts:192; PUBLICBOOKING_GOOGLE_REDIRECT_URI=vibrant-wellness.mypatienthubs.com |
| Provider-portal OAuth redirects | — | config: GOOGLE_REDIRECT_URI=staging.va-portal.pages.dev, OUTLOOK_REDIRECT_URL=…/oauth/outlook-web, ZOOM_REDIRECT_URI=api.vibrant-wellness.com/lis-sure-script/routing |
| EHR service | GraphQL | calendar-sync.resolver comment "EHR-facing helper" |
| Google / Microsoft | webhooks | §4.5 |

Distinct legacy service: `Portal-Calendar` repo answers `/v1/portal/calendar/*/clinicians/first-available` — NOT transformer-v2 (see LTM repos.md). config also references `va_events = api.vibrant-wellness.com/v1/portal/calendar/events/samples/get-events` (separate calendar service consumed elsewhere in trans).

---

## 11. Magic constants & gotchas

- **`CLINICIAN_PRACTICE_ID = 150105`** ("Vibrant Clinical Team") hardcoded in reminder/accession-claim/daily-report constants; gates *ByPatient event mutations, reminders, daily report, accession claiming, clinician email-template override.
- `v2_event` has NO status enum — only `is_canceled`. Reschedule (clinician switch) = cancel-and-rebook, so "cancelled" rows ≠ user cancellations.
- Two email topic casings: Azure `notification-email-template` vs on-prem `'Notification-Email-Template'` — different clusters, both intentional.
- Settings live on `v2_calendar` columns; `v2_user_settings` / `v2_event_type_color_override` are dead (stale comment at user-settings.service.ts:527).
- Availability fallback Mon–Fri 9–5 when provider has no `v2_schedule` rows.
- Pending meeting requests BLOCK availability slots (not just confirmed events).
- CORS wide open at app level; public surface protected only by rate limit + gateway.
- `openapi.yml` documents GET /csrf-token that doesn't exist.
- `ical-generator` dependency unused. Zoom orphan cleanup method exists but is not scheduled.
- Multi-pod (3 replicas) safety patterns: reminder idempotency_key UNIQUE, daily-report Redis NX day lock, accession UNIQUE claim in transaction.
- Zoom JWT secret: stprod ⇒ secretOrKeyDev, else secretOrKeyProd.
- prisma sequences still named `calendar_dev_new.*` in prod defaults (schema was copied); harmless but confusing.

## 12. Prod usage snapshot (queried 2026-07-28, calendar_prod)

- Events/month (start_time): 2026-01: 104, 02: 979, 03: 1,104, 04: 895, 05: 794, 06: 895, 07: 786; future-dated tail through 2026-12 + one 2027-05. `is_canceled` counts tiny (≤7/mo) — real cancels mostly live as exceptions/cancel-and-rebook.
- Event types: Call 2,417; Zoom Meeting 1,434; Clinical Consult 1,191; Follow-up 283; Meeting 181; VCT 165; Sales Event 154; Zendesk/Teams 129; Task 120; General 118.
- Calendars: 48,800 total (patient 27,736 / clinicadmin 12,482 / provider 8,582; all is_active) across 32,429 distinct owners / 18,129 practices — mostly bootstrap. **Only 764 calendars have ever created events, across 4 practices** ⇒ real usage concentrated in Clinical Team consults.
- Integrations: 44 rows (zoom 24, google 19, outlook 1). Events synced externally: google_event_id 17, outlook_event_id 94, zoom_event_id 0 (zoom links likely stored as external_url/manual).
- Empty-but-live features: v2_meeting_request, v2_meeting_type*, v2_clinic_location, v2_clinic_settings.

## 13. Related tickets / history anchors

VP-16410 (accession 1:1 claim), VP-16463 (nearby: emr-v2 cutover — different module), VP-16512/16514 (meeting types), VP-16520/16521 (Clinical Consult reschedule, cancel-and-rebook design), VP-16547/16558 (RS256 auth), VP-16612 (exclude clinicadmin from reminders), VP-16685 (gRPC cloud fallback), VP-16850 (public booking slot validation + verify scripts in `scripts/`), VP-17065 (daily report; PR #531 External_url), VP-17190 (timezone source of truth), VP-17261/17272 (checkCustomerAccess patient_id), VP-17421 (legacy Bull reminder incident — belongs to LIS-transformer, NOT this repo), PR #515 (disable introspection).

Related STM/LTM: `long-term-memory/repos.md` §LIS-transformer-v2 (prod DB connection recipe, reschedule design), `patterns.md` (consult reminder dual-producer fingerprint).
