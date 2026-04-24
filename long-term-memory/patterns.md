---
id: patterns
type: ltm
category: repo_patterns
status: active
score: 0.1089
base_weight: 0.8
created: 2026-04-22
updated: 2026-04-22
links: []
tags:
- patterns
- build
- deploy
- investigation
summary: Build/deploy patterns, investigation flows, DB connections, known issues
---



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

### gRPC from Standalone Scripts
- NestJS `createApplicationContext` 不初始化 gRPC `@Client` decorator — migration script 無法透過 NestJS DI 取得 gRPC service
- 解法：用 `@grpc/grpc-js` + `@grpc/proto-loader` 直接建 client 連 `192.168.60.6:30276`（見 `emr-integration.md`）
- 需要 OAuth2 metadata: `authorization` (Bearer), `x-request-id`, `internal-user-id`, `service-name`
- OAuth2 token: client_credentials grant，env vars `OAUTH2_CLIENT_ID` / `OAUTH2_CLIENT_SECRET` / `OAUTH2_TOKEN_ENDPOINT`
- `.env` 裡的 gRPC URL 可能是 Azure 內網 IP（如 `CORE_SAMPLE_V2_RPC`），本機連不到 — **永遠用 knowledge 記載的 endpoint**

### ehr_vendors Legacy Data
- `ehr_vendors.code` 欄位有 mixed case（`ElationEMR`, `OptimalDX`, `ChARM_EHR`, `HealthMatters`）
- `CreateEhrVendorDto` 強制 `^[A-Z_]+$` 只對新建的 vendor 有效，legacy data 不受約束
- 寫 migration SQL 時**必須查實際 DB**，不能只看 repo 的 migration scripts（scripts 只涵蓋部分 vendor）
- 查 vendor 用 `npx ts-node` script + Prisma `$queryRaw` 最快

### Data Migration 安全模式
- 新增 boolean filter 欄位時，先 `UPDATE ALL SET col = FALSE`，再 `UPDATE known SET col = TRUE`
- 比反向（default TRUE + exclude known）安全：避免遺漏未知資料

### 更新 DB 前先查現有命名慣例
- 批次 UPDATE 類別（如 calendar name, display label）前，先 `SELECT DISTINCT col FROM table` 看既有格式
- 不要從 ticket 描述或 API 命名猜測，legacy 資料可能有特殊慣例（如 "{NAME}'s Patient Calendar" vs "{name}'s Provider Calendar"）
- VP-16232 因未確認命名慣例而誤改 5,027 筆 patient calendar 為 "Provider Calendar"

### lis-backend-emr-v2 Vendor API 架構
- `EhrVendorService.findAll()` → 只服務 `GET /ehr-vendors` HTTP endpoint（Settings 頁面）
- `admin-portal/vendor-management.service.ts` → 獨立 service，有自己的 `findAllVendors()`
- HL7 encoder、result generation、ChARM detection → 直接用 `prisma.ehrVendor.findFirst()` 或 relation include
- 修改 `findAll()` 的 filter 邏輯**不會影響**內部 vendor lookup

### mysql2 Timezone
- Legacy MySQL datetime 欄位存 UTC 但無 timezone info
- mysql2 連線必須加 `timezone: '+00:00'` 才能正確讀取 UTC 值
- 不加的話預設用本機時區（如 PST）解讀，導致時間偏移
