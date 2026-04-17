# Common Patterns & Gotchas

---

## NestJS Projects 共通
- `npx prisma generate` after schema changes
- Dual Prisma: generate both schemas separately, import client2 from `prisma2/generated/client2`
- Jest testing: co-located `*.spec.ts`
- Docker: multi-stage build (node builder → alpine runtime)

## Go Projects (coreSamples)
- `make proto` for protobuf, `make ent` for ORM
- Testing: in-memory SQLite via `enttest`

## Gotchas

### Prisma Dual Schema
- LIS-transformer-v2: `prisma/` (PostgreSQL) + `prisma2/` (MySQL)
- LIS-setting-consumer: `prisma/` (primary) + `prisma2/` (transactions)

### Kafka Consumer Groups
- Group ID 必須完全匹配 config 和 controller
- LIS-setting-consumer 有 20+ topics — 改動要小心

### Large Files（不要整檔讀取）
- `LIS-transformer/src/trans/trans.service.ts` ~4000 lines
- `LIS-setting-consumer/setting-consumer.controller.ts` ~16K lines

### TypeScript
- 大部分專案 `strictNullChecks: false`, `noImplicitAny: false`
- 不要主動引入 strict typing

### Environment Variables
- 各專案用不同的 env var 名稱：`NODE_ENV` / `SERVER_ENVIRONMENT` / `DEPLOY_ENVIRONMENT` / `platform_type`
