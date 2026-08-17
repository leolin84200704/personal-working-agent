---
name: feedback_schema_migration_before_deploy
description: "emr-v2 prod isn't Prisma-managed — apply schema-adding ALTER to prod DB before/with the code deploy or every read 500s"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 99dcff7b-017c-4aa9-b3ee-802733ba4be2
---

lis-backend-emr-v2 的 prod DB **不是 Prisma Migrate 管理的**（`_prisma_migrations` 空，`migrate status` 全 unapplied，schema 靠手動 ALTER）。所以當 ticket 在 `schema.prisma` 對某 model 加一個 **non-optional scalar 欄位**，那個 ALTER 必須在 code deploy **之前或同時**手動 apply 到 prod DB —— 否則 deployed Prisma client 的預設 SELECT 會帶上該欄位，prod DB 無此欄 → MySQL `Unknown column` → **該 model 的每個 findMany/findFirst 都 500**（不只新功能，連既有 list / order 解析等全掛）。

**Why:** VP-16832 加了 `EhrIntegration.gz_ny_routing_enabled Boolean @default(false)`，STM 一直把「apply column」列為 pending deploy 前置。#168 被 merge+部署後沒先 apply → prod 500 on GET /integration-management/auto-integrate/requests，且連 order 解析（customer-detail-fetcher / resolveIntegration 都查 ehr_integrations）一起中。修復 = idempotent `ALTER TABLE ehr_integrations ADD COLUMN gz_ny_routing_enabled TINYINT(1) NOT NULL DEFAULT 0`（= Prisma Boolean @default(false)）。

**How to apply:** (1) 任何改 `schema.prisma` 加欄位的 ticket，把「prod DB apply ALTER」當**硬 deploy gate**，不是 nice-to-have；merge/deploy 前先確認 prod DB 已有該欄（`SELECT ... information_schema.COLUMNS`）。(2) 部署後若某 endpoint 突然 500（非 403），先比對 deployed `schema.prisma` 該 model 的 scalar 欄位 vs prod DB `information_schema.COLUMNS`，找 missing column（idempotent ALTER 補）。(3) Boolean@default(false)→`TINYINT(1) NOT NULL DEFAULT 0`，既有列得 false 安全。同源於 [[feedback_config_yaml_coupling_with_code]]（code 與 infra/DB 狀態必須同步）。prod 連線/驗證見 [[reference_azure_mysql]]。
