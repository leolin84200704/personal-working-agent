# MEMORY - Knowledge Index

> Agent's accumulated knowledge index. Every memory is learned from actual operations.

---

## Index

- [Repos](#repos) - Understanding of each repo's function and architecture
- [Patterns](#patterns) - Common modification patterns and practices
- [Gotchas](#gotchas) - Pitfalls and things to watch out for
- [Questions](#questions) - Questions asked and answers received
- [Jira](#jira) - Jira-related knowledge

---

## Repos

### Active Repos (with content)

#### LIS-transformer-v2
- **Purpose**: LIS frontend GraphQL API gateway integrating multiple backend microservices
- **Tech Stack**: NestJS 11, TypeScript, Node.js 20, Prisma (dual databases)
- **Port**: 3390 (GraphQL + REST at `/api`)
- **Key Files**:
  - `src/main.ts` - Bootstrap (port, middleware, Sentry)
  - `src/app.module.ts` - Root module with GraphQL, modules
  - `src/trans/` - Core LIS: orders, patients, settings, merchandise (~4000 lines)
  - `src/calendar/` - Scheduling: Google, Outlook, Zoom integrations
  - `src/questionnaire/` - Surveys and forms
  - `src/setting/` - Provider/clinic settings, 2FA, Twilio phones
  - `src/patientvariable/` - Patient variables for encounter notes
  - `src/role/` - RBAC role management
  - `src/vitals/` - Patient vital signs
  - `prisma/schema.prisma` - Calendar DB (PostgreSQL)
  - `prisma2/schema2.prisma` - Main LIS DB (MySQL)
  - `protos/` - gRPC definitions (25 files)
  - `protos2/` - gRPC definitions v2 (24 files)
- **Databases**:
  - PostgreSQL via `@prisma/client` (Calendar)
  - MySQL via `@prisma/client2` (Main LIS)
- **gRPC Services**: Core LIS, Core Samples V2, Test Results, Shipping, Dashboard, Issue System, Audit Log
- **Infrastructure**: Redis (Azure with Managed Identity), Consul, Kafka, Sentry
- **GraphQL**: Code-first with Apollo Server, JWT context
- **Command**: `npm run start:dev` (run `npx prisma generate` for both schemas first)

#### LIS-transformer
- **Purpose**: NestJS backend service for LIS, REST (port 3190) + gRPC (port 3191)
- **Tech Stack**: NestJS 10, TypeScript, Node.js 16, Prisma
- **Key Files**:
  - `src/main.ts` - Bootstrap (Express on :3190, gRPC on :3191, Swagger at `/api`)
  - `src/trans/` - Core patient data transformation, timelines, tube mapping
  - `src/setting/` - Clinic settings (account, billing, test ordering, PNS)
  - `src/auth/` - JWT + Passport authentication
  - `src/utility/` - CSV processing, Kafka consumers
  - `prisma/schema.prisma` - Primary MySQL DB
  - `prisma/calendar.prisma` - Calendar DB
- **Services**: ~20 downstream microservices via gRPC
- **Kafka**: Dual setup (local/cloud SASL, Azure connection string)
- **PDF**: IronPDF with platform-specific engines
- **Command**: `npm run start:dev`

#### EMR-Backend
- **Purpose**: Java-based EMR order parsing and processing
- **Tech Stack**: Java 8, Maven 3.6.0, MyBatis ORM, gRPC
- **Build**: `mvn package` generates `emr-0.0.1-SNAPSHOT-jar-with-dependencies.jar`
- **Entry Point**: `com.vibrant.emr.EmrOrderTask.ParseOrder`
- **Plugins**:
  - `mybatis-generator` - Generates Mybatis ORM code (`com.vibrant.emr.entity`, `com.vibrant.emr.mapper`)
  - `protobuf` - Generates gRPC code
- **Key**: Run plugins manually before `mvn package`

#### lis-backend-emr-v2
- **Purpose**: Healthcare EMR System Backend with AutoIntegrate functionality
- **Tech Stack**: NestJS, TypeScript, MySQL 8.0, Prisma, Apache Kafka, JWT
- **Port**: 3000, Swagger at `/api/docs`
- **Key Modules**:
  - `ordering/` - Order management
  - `result/` - Lab result management
  - `hl7/` - HL7 encoding/decoding/validation
  - `sftp/` - SFTP connections and file transfers
  - `kafka/` - Event-driven messaging
  - `integration-management/` - AutoIntegrate + Admin Portal
  - `customer-portal/` - Independent customer portal (retransmission, dashboard)
- **Database**: Prisma with MySQL 8.0
- **Command**: `npm run start:dev` (run `npx prisma:generate` first)
- **Approach**: TDD (Test-Driven Development)

#### LIS-setting-consumer
- **Purpose**: Kafka consumer microservice for LIS events, dispatches notifications via Bull/Redis
- **Tech Stack**: NestJS 9.3, TypeScript 4.7, Node.js 16, Prisma (dual schemas)
- **Port**: 6457
- **Architecture**:
  1. Kafka consumers (20+ topics) → Validate & enrich via gRPC
  2. Bull queues (Redis Sentinel) → Async notification jobs
  3. Bull processors → Email, SMS, push notifications
- **Key Files**:
  - `src/setting-consumer/setting-consumer.controller.ts` - Main Kafka consumer (~16K lines!)
  - `src/setting-consumer/bull.consumer.ts` - 20+ Bull processors
  - `prisma/schema.prisma` - Primary MySQL DB
  - `prisma2/schema2.prisma` - Secondary MySQL (transactions/audit)
  - `protos/` - gRPC definitions (23 proto files)
- **Bull Queues**: notify_patient_pay, notify_customer_when_lab_issue, remindScheduleConcierge, pediatric_consent_notification_queue, etc.
- **gRPC Services**: Core LIS, Issue Service, Audit Service
- **Health**: `/health` endpoint + Kafka consumer monitoring cron (every 2 hours)
- **Command**: `npx prisma generate` && `npx prisma generate --schema=prisma2/schema2.prisma` then `npm run start:dev`

#### LIS-backend-v2-coreSamples
- **Purpose**: Core laboratory samples, orders, customers, clinics management
- **Tech Stack**: Go 1.19+, go-micro v4, Ent ORM, MySQL, Redis, Kafka
- **Ports**: gRPC 8084, HTTP 8083
- **Architecture**:
  - `handler/` - HTTP/gRPC request handlers
  - `service/` - Business logic
  - `ent/schema/` - Database schema definitions
  - `publisher/` - Kafka publishers
  - `subscriber/` - Kafka consumers
  - `tasks/` - Asynq background jobs
  - `processor/` - Data transformation
- **Key Services**: OrderService, CustomerService, PatientService, SpecimenService, RequiredTubeVolumeService
- **Infrastructure**: Consul, Redis, Kafka, MySQL, Jaeger (tracing), Sentry
- **Rate Limit**: 100 QPS
- **Command**: `./dev.sh` (requires `make proto` && `make ent` first)
- **Env**: `CORESAMPLES_ENV` (dev, staging, aks_staging, aks_production)

### Empty/Placeholder Repos

These repos appear to be empty or minimal:
- **EHR-backend** - Contains only NestJS template README
- **LIS-backend-billing** - Empty
- **LIS-backend-coreSamples** - Empty
- **LIS-backend-v2-order-management** - Empty
- **Portal-Calendar** - Does not exist

---

## Patterns

### NestJS Projects (LIS-transformer, LIS-transformer-v2, lis-backend-emr-v2, LIS-setting-consumer)
- **Entry Point**: `src/main.ts` for bootstrap, middleware, Sentry
- **Module Structure**: Controllers → Services → DTOs pattern
- **Prisma**: Always run `npx prisma generate` after schema changes
- **Dual Prisma**: Some projects use two schemas (generate both separately)
- **gRPC**: Proto files in `protos/` directory, options in `src/grpc.option.ts`
- **Testing**: Jest with co-located `*.spec.ts` files, E2E in `test/`
- **Docker**: Multi-stage build (node builder → alpine runtime)

### Java/Maven Projects (EMR-Backend)
- **Build**: `mvn package`
- **Plugins**: Run mybatis-generator and protobuf manually before build
- **Entry Point**: Specified in pom.xml, run with `java -cp jar`

### Go Projects (LIS-backend-v2-coreSamples)
- **Code Gen**: `make proto` for protobuf, `make ent` for ORM
- **Testing**: In-memory SQLite via `enttest`, mock Redis with `tempredis`
- **Background Jobs**: Asynq for async tasks

---

## Gotchas

### Prisma Dual Schema
- **LIS-transformer-v2**: `prisma/` (PostgreSQL) and `prisma2/` (MySQL) - must generate both
- **LIS-setting-consumer**: `prisma/` (primary) and `prisma2/` (transactions) - must generate both
- Import client2 from custom path: `prisma2/generated/client2`

### Kafka Consumer Groups
- Consumer group IDs must match exactly between config and controller
- Changes to consumer groups affect production message processing
- LIS-setting-consumer has 20+ topics - critical infrastructure

### Large Files
- `LIS-transformer/src/trans/trans.service.ts` ~840KB (~4000 lines)
- `LIS-transformer-v2/src/trans/trans.service.ts` ~4000 lines
- `LIS-setting-consumer/src/setting-consumer/setting-consumer.controller.ts` ~16K lines
- Read specific line ranges, not entire files

### TypeScript Strict Mode
- Most projects have `strictNullChecks: false` and `noImplicitAny: false`
- Don't introduce strict typing unless asked

### Environment Variables
- `NODE_ENV` vs `SERVER_ENVIRONMENT` vs `DEPLOY_ENVIRONMENT` vs `platform_type`
- Check which project uses which convention

---

## Questions

### Q: How to determine which repo to modify for a ticket?
> **A**:
> 1. Check ticket project key (LIS, EMR, etc.)
> 2. Check ticket keywords:
>    - "calendar", "schedule", "appointment" → LIS-transformer-v2 calendar module
>    - "HL7", "transform" → LIS-transformer
>    - "order", "sample", "patient" → LIS-backend-v2-coreSamples
>    - "notification", "email", "SMS" → LIS-setting-consumer
>    - "EMR", "AutoIntegrate" → lis-backend-emr-v2
> 3. Search relevant files in identified repos

### Q: What to do when Prisma schema changes?
> **A**:
> 1. Run `npx prisma generate` for default schema
> 2. If project has dual schemas, also run `npx prisma generate --schema=prisma2/schema2.prisma`
> 3. Restart the dev server

---

## Jira

### Project Keys
- **LIS** - LIS related projects (transformer, samples, billing, etc.)
- **EMR** - EMR related projects

### Custom Fields
- `customfield_10000` - Sprint

---

## Ticket → Repo Mapping Guide

| Ticket Keywords | Likely Repo | Module/Path |
|----------------|-------------|-------------|
| calendar, schedule, appointment, Google, Outlook, Zoom | LIS-transformer-v2 | `src/calendar/` |
| GraphQL, patient order, merchandise, PNS, setting | LIS-transformer-v2 | `src/trans/` |
| questionnaire, survey, form | LIS-transformer-v2 | `src/questionnaire/` |
| provider setting, 2FA, Twilio, email branding | LIS-transformer-v2 | `src/setting/` |
| patient variable, encounter note | LIS-transformer-v2 | `src/patientvariable/` |
| role, permission, RBAC | LIS-transformer-v2 | `src/role/` |
| vital sign, BMI | LIS-transformer-v2 | `src/vitals/` |
| HL7, transformation | LIS-transformer | `src/trans/` |
| clinic setting, billing, test ordering | LIS-transformer | `src/setting/` |
| EMR order, AutoIntegrate | lis-backend-emr-v2 | `src/modules/integration-management/` |
| sample, order, patient (core) | LIS-backend-v2-coreSamples | `service/` |
| notification, email, SMS, push | LIS-setting-consumer | `src/setting-consumer/` |
| result ready, shipment, kit, billing | LIS-setting-consumer | Kafka topics |
| Java, gRPC proto | EMR-Backend | `com.vibrant.emr.*` |

---

*This file grows with every interaction. Last Updated: 2026-04-06*
