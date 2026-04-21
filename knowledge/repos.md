# Repo Reference

> Quick reference for each repo. Read repo source code directly for detailed structure.

---

## Active Repos

### LIS-transformer-v2
- **Purpose**: LIS frontend GraphQL API gateway
- **Tech**: NestJS 11, TypeScript, Prisma (PostgreSQL + MySQL dual schema)
- **Port**: 3390
- **Key Areas**: `src/trans/` (orders/patients), `src/calendar/`, `src/setting/`, `src/questionnaire/`
- **Setup**: `npx prisma generate` for both schemas, then `npm run start:dev`
- **Migration scripts**: `scripts/` 目錄（standalone ts-node）或 `src/calendar/migration/`（NestJS service，但 gRPC 不可用）

### LIS-transformer
- **Purpose**: NestJS backend, REST (3190) + gRPC (3191)
- **Tech**: NestJS 10, TypeScript, Prisma
- **Key Areas**: `src/trans/` (patient data), `src/setting/` (clinic settings)
- **Note**: `src/trans/trans.service.ts` ~4000 lines

### lis-backend-emr-v2
- **Purpose**: EMR system backend (AutoIntegrate)
- **Tech**: NestJS, TypeScript, MySQL 8.0, Prisma, Kafka
- **Port**: 3000
- **Key Areas**: `src/modules/ordering/`, `src/modules/result/`, `src/modules/hl7/`, `src/modules/integration-management/`
- **Scripts**: `scripts/insert-ehr-integration.ts`, `scripts/insert-order-client.ts`, etc.

### LIS-backend-v2-coreSamples
- **Purpose**: Core lab samples, orders, customers
- **Tech**: Go 1.19+, go-micro v4, Ent ORM, MySQL, Redis, Kafka
- **Ports**: gRPC 8084, HTTP 8083
- **Setup**: `make proto && make ent && ./dev.sh`

### EMR-Backend
- **Purpose**: Legacy Java EMR order parsing (being migrated to emr-v2)
- **Tech**: Java 8, Maven, MyBatis, gRPC
- **Build**: Run mybatis-generator + protobuf plugins, then `mvn package`

### LIS-setting-consumer
- **Purpose**: Kafka consumer for notifications (email, SMS, push)
- **Tech**: NestJS 9.3, Bull/Redis queues, 20+ Kafka topics
- **Port**: 6457
- **Note**: `setting-consumer.controller.ts` ~16K lines

## Inactive/Empty
- EHR-backend, LIS-backend-billing, LIS-backend-coreSamples, LIS-backend-v2-order-management — empty or minimal
