---
id: repo-catalog
type: ltm
category: technical
status: active
score: 0.6794
base_weight: 0.9
created: 2026-06-07
updated: 2026-06-07
links:
- INCIDENT-20260518
- INCIDENT-20260528
- INCIDENT-20260601-sftp-hang
- INCIDENT-20260604
- LBS-1547
- PO-222
- QH-1104
- QH-1130
- QH-1159
- QH-1591
- QH-1860
- QH-211
- QH-2259
- QH-2648
- QH-680
- QH-862
- QH-918
- QH-919
- VP-15460
- VP-16009
- VP-16154
- VP-16164
- VP-16165
- VP-16168
- VP-16169
- VP-16172
- VP-16232
- VP-16391
- VP-16410
- VP-16499
- VP-16512
- VP-16513
- VP-16514
- VP-16516
- VP-16520
- VP-16521
- VP-16629
- VP-16759
- VP-16760
- VP-16784
- VP-16785
- VP-16786
- VP-16787
- VP-16850
- VP-16859
- VP-16921
- VP-16945
- business-model
- business-model-deep
- emr-integration
- failures
- patterns
- repos
tags:
- repos
- catalog
- architecture
- ecosystem
- microservices
summary: 'Org-wide repo catalog: every Vibrant-America LIS repo — service type, purpose/本質,
  tech, ports, data stores, role in ecosystem. Companion to repos.md (which holds
  deep gotchas for actively-worked repos).'
---





















































# Vibrant America — 全 Repo 服務目錄 (Repo Catalog)

> 目的：快速理解「這間公司每個 repo 是什麼服務、本質為何、在 LIS 生態系的角色」，解 ticket 時用來定位服務。
> 來源：2026-06-07 對 31 個近兩週有更新的 repo 做唯讀掃描彙整（org 共 153 repo，此處涵蓋活躍主力）。
> **與 `repos.md` 的分工**：`repos.md` 是「正在開發中 repo」的深度 operational gotcha（build/prisma/race condition…）；本檔是「全公司服務地圖」總覽。深度細節仍以 `repos.md` 為準。
> ⚠️ Default branch 各 repo 不同（main / master / stage_test），開 branch / PR 前先確認。

---

## 生態系全景 (Ecosystem Overview)

**技術世代分層**：
- **v2 重寫世代（Go, go-micro v4 + Ent + Gin）**：財務與目錄類微服務 — order-management / billing / charging / payout / pricing / Lab-test / RBAC。容器內 HTTP 多為 `8084`，gRPC `8085`，靠 k8s service 區分。
- **NestJS 世代（TypeScript + Prisma）**：核心領域服務 — coreSamples / Sample / Shipping / Report / notification-center / dashboard / results-* / transformer* / emr-v2。
- **Legacy（被汰換中）**：labsiteAPI（Python Falcon 巨石）、EMR-Backend（Java）、LIS-backend-billing（Java Spring）、LIS-accounting-wsgi（Python，標 "RETIRE FOR GOOD"）、LIS-backend-coreSamples↔被 v2-coreSamples 取代中。
- **Rust**：OAuth（唯一 Rust 服務，authz 中樞）。

**主要資料流（典型 patient order）**：
```
患者下單 → PNS-Singlepage(前端) → v2-order-management → 
  charging(收款) → billing(發票/結算) → payout(撥款給診所/抽血師)
  └ pricing(定價/promo) ← 查詢
sample 生命週期 → LIS-Sample / LIS-Shipping(物流) → 儀器 tcp-di(ASTM) → 
  results-core/grpc(結果) → LIS-Report→report-pdf+report-pdf-engine(PDF) → 患者
事件總線：各服務 → Kafka / Azure Event Hub → LIS-backend-dashboard + Message-clone → ClickHouse(分析)
通知：各服務 → Kafka → LIS-notification-center / LIS-setting-consumer → Postmark/Vonage
authz：所有服務 → OAuth(token) + Vibrant-RBAC(權限) 把關
```

**橫切關注 (cross-cutting)**：OAuth(認證)、Vibrant-RBAC(授權)、dataContracts(schema 契約)、va-responsive-components-library(前端 UI 共用)、Message-clone(事件落 ClickHouse)、TestRepo(E2E QA)。

---

## 1. LIS v2 財務微服務群 (Go / go-micro v4 / Ent / Gin)

> 共通：Go 1.23-1.25、Ent ORM + MySQL、Redis、Kafka、Consul config。容器內 HTTP 多 `8084`。彼此用 gRPC/HTTP 串接，組成 order→charging→billing→payout 金流鏈。

### LIS-backend-v2-order-management
- **Default branch**: main | **Tech**: Go 1.24 / Gin + go-micro v4 | **Type**: backend-microservice
- **本質**: LIS v2 訂單生命週期中樞（kit 物流、患者關聯、訂閱、PDF、async 處理）。
- **責任**: Order CRUD/狀態追蹤；kit 庫存/出貨標籤/redraw；訂閱排程；PDF（標籤/抽血表/摘要）；Asynq async worker；Kafka 事件；Temporal workflow。
- **介面**: HTTP 8084；gRPC clients → Core/Issue/Tube/Result；OpenAPI `openapi-spec.yaml`。
- **資料**: MySQL(Ent, 26 entity)、Redis(cache+Asynq)、Kafka(accounting/result/legacy)、Azure Event Hub、Cloudflare R2(PDF)。
- **生態角色**: 中央訂單樞紐；呼叫 Accounting/Charging/Inventory/Shipping/Result；產生下游 billing/payout 事件。
- **活躍度**: Active(2026-06-05)；~140K LOC(不含 ent-gen)；production critical。

### LIS-backend-v2-billing
- **Default branch**: main | **Tech**: Go 1.24 / Gin + go-micro v4 | **Type**: backend-microservice
- **本質**: 財務交易管理（invoice/payment/settlement/credit/tax），Stripe 整合。
- **責任**: Charge(invoice) 建立/折扣；Payment(receipt) 處理/退款/轉帳；Apply(結算) 沖帳餘額；credit memo；多幣別(8+)；Stripe/Stax webhook；Kafka 發佈。
- **介面**: HTTP 8084；gRPC → Core/Audit；HTTP → Order/Setting/Sample/Transaction；OpenAPI `docs/openapi.yaml`；Swagger `/swagger/index.html`。
- **資料**: MySQL(Ent, 9 entity: Apply/Charge/Credit/Discount/ExchangeRate/Payment/PaymentV2/Tax/BillingSnapshot)、Redis(lock)、Kafka(accounting)、Stripe。
- **生態角色**: Order 下游；提供 balance/credit API 給 charging；發 accounting 事件給 payout。
- **活躍度**: Active(2026-06-03)；~83K LOC。**Notable**: v1/v2/v3 多版本 route；Redis lock 結算；Consul config。

### LIS-backend-v2-charging
- **Default branch**: main | **Tech**: Go 1.24 / Gin + go-micro v4 | **Type**: backend-microservice
- **本質**: 收款/支付閘道編排（Stripe/Stax/內部），管理 customer info、付款方式、訂閱。
- **責任**: 付款方式(card/ACH/BNPL/credit)；payment intent；交易/退款/轉帳；數位錢包(Apple/Google Pay)；HFSA/BNPL；訂閱循環扣款；批次扣款(cron+Redis lock)；webhook 簽章驗證；gRPC audit。
- **介面**: HTTP 8084；gRPC → Core/Issue/Audit；HTTP → Order/Accounting/Statement/UserPilot；Swagger `/v1/charging/swagger/index.html`。
- **資料**: MySQL(Ent, 9 entity)、Redis Sentinel(批次 lock)、Kafka、Stripe/Stax。
- **生態角色**: Accounting 的上游（扣款觸發 accounting 事件）；呼叫 Order；與 Billing 共享 payment 平台資料。
- **活躍度**: Active(2026-05-29)；~88K LOC。

### LIS-backend-v2-payout
- **Default branch**: main | **Tech**: Go 1.23 / Gin + go-micro v4 | **Type**: backend-microservice
- **本質**: 下游撥款/結算（付款給 vendor/抽血師/診所），Stripe Connect onboarding + Accounting credit 生命週期。
- **責任**: Stripe Connect Express 開戶；payout transfer(cashout/profit/merchandise/rewards) 與狀態；waitlist 資格檢查 + credit 狀態轉換；Stripe Connect webhook；消費 Order 事件觸發資格檢查；Asynq；與 Accounting credit create/update/void。
- **介面**: HTTP 8084；gRPC → Core(TNP results)；HTTP → Order/Accounting/Phlebotomy；Kafka consumer(lis-general-events)。
- **資料**: MySQL(Ent, 12 entity)、Redis、Kafka、Stripe(standard+Connect)。
- **活躍度**: Active(2026-06-02)；~10K LOC(群中最小)；**fail-closed 保守設計**避免重複撥款。

### LIS-backend-v2-pricing
- **Default branch**: main | **Tech**: Go 1.24 / Gin + go-micro v4 | **Type**: backend-microservice（HTTP+gRPC）
- **本質**: data-driven 定價/促銷引擎（catalog、price、promotion/coupon、shipping quote、tax）。
- **責任**: Item/shortcut(預設 bundle) 管理 copy/restore；price/package/currency；promotion/coupon 驗證+用量；merchandise；FedEx 運費 quote；Stripe Tax 稅；markup scheme；gRPC tax/pricing 查詢。
- **介面**: HTTP 8084 + **gRPC 8085**；Swagger `/swagger/index.html`。
- **資料**: MySQL(Ent, 25 entity)、Redis(TTL 11-168h 依波動)、Kafka(pricing_service)、Stripe Tax、FedEx、**legacy LISRE DB(唯讀)**。
- **生態角色**: 提供 pricing/tax API 給 Charging/Order；購買流程套用促銷。
- **活躍度**: Active(2026-05-27)；~19K LOC。**Notable**: 改 DB 紀錄優先於改 code；read-through cache。

---

## 2. LIS 核心領域服務 (NestJS/Go — sample/test 生命週期)

### LIS-backend-coreSamples
- **Default branch**: main | **Tech**: NestJS 10 + Prisma 4.16 + MySQL | **Type**: REST + gRPC
- **本質**: 核心 LIS — sample/test/patient/customer/clinic/reference range 管理。
- **介面**: REST 5274、gRPC 5900。
- **資料**: MySQL(多 schema Prisma: main + prisma2-6 做 3NF/table split)、Redis(Bull+cache)、Kafka、ClickHouse。
- **生態角色**: 主核心服務；經 gRPC 整合 RBAC/audit/shipping/translation；發事件到 Kafka。
- **活躍度**: Active(2026-06-05)；131K+ LOC。**Notable**: 近期移除 Consul 改用直接 env var。
- ⚠️ 注意：與 Go 版 `LIS-backend-v2-coreSamples`（見 repos.md，Go/Ent，gRPC 8084/HTTP 8083）平行存在 — 一個 NestJS、一個 Go v2，確認 ticket 指哪個。

### LIS-Sample
- **Default branch**: **master** | **Tech**: NestJS 9.2.1 | **Type**: REST + gRPC
- **本質**: sample order 管理、患者資料、tube 庫存、儲位追蹤、客戶互動。
- **介面**: HTTP 6300(`/api` swagger)、gRPC、Kafka、Azure Service Bus。
- **資料**: 3 個 MySQL(master-slave: lis_inventory / vibrant_tracking / vibrant_america_information，6 Prisma client)、Redis、Consul。
- **活躍度**: Active(~2026-06-05)；19.8K LOC。**Notable**: 讀寫分離；Kafka outbox pattern；26+ proto。

### LIS-Shipping
- **Default branch**: **master** | **Tech**: NestJS 9.2.1 | **Type**: REST + gRPC + WebSocket
- **本質**: sample 物流/出貨/追蹤/kit 管理/carrier(FedEx/DHL) 整合。
- **責任**: order/shipment、tube 處理、kit 配送、issue 追蹤、pickup 排程、運費計算、批次 PDF、carrier API。
- **介面**: HTTP 6256、gRPC 63142、WebSocket(Socket.IO 即時通知)、Kafka、Azure Event Hub。
- **資料**: **8 個 MySQL**(最大 DB footprint)、Redis(Bull)、FTP、AWS S3。
- **活躍度**: Active(~2026-05-28)；67.6K LOC。**Notable**: dual-version(issues.v2/pickups.v2)；rate limit 3000/60s；46 proto。

### LIS-Lab-test
- **Default branch**: main | **Tech**: Go 1.25 / go-micro v4 | **Type**: gRPC microservice(無 REST)
- **本質**: 檢驗 test catalog 與 metadata 權威源（test-code mapping、assay group、reference/optimal range、tube spec）。
- **介面**: **gRPC 8084(唯讀，無 REST)**；Kafka(CDC/系統事件)、Asynq、Jaeger、Sentry。
- **資料**: MySQL(Ent, 13+ entity)、Redis(兩層 cache：memory+Redis，跨 pod Kafka 失效)。
- **生態角色**: 所有 LIS consumer 的 test metadata/range 權威源；整合 coreSamples v1/v2、Questionnaire。
- **活躍度**: Active(~1 天前)；128.4K LOC。**Notable**: 排程 deferred update(在 effective_date 由 Asynq 執行)；dual Kafka publisher(local+cloud)。

---

## 3. 報告與 PDF 渲染 (Reporting & PDF)

### LIS-Report
- **Default branch**: main | **Tech**: NestJS 9 (Node 22.16) | **Type**: 微服務(REST + 多 gRPC client)
- **本質**: PDF 報告產生/版控/快取（27+ 報告類型 VA/FZ/TG/TB…），客戶端報告交付。
- **介面**: HTTP 3020(REST，無 gRPC server)、Azure Event Hub、Kafka、ClickHouse HTTP、10+ gRPC client、Redis。
- **資料**: Prisma(main) + Prisma5(report version cache)、ClickHouse、Redis(on-prem Sentinel / cloud Azure Redis Enterprise)、R2/Cloudflare(PDF)、Azure App Config+Key Vault(cloud)。
- **生態角色**: sample/test/result 的終端 consumer；產報告後發 Kafka 事件；是 `LIS-interactive-report`(前端) 的後端對應。
- **活躍度**: Active(~2026-06-04)；173K LOC。**Notable**: 雙設定系統(on-prem Consul / cloud Azure App Config)；Puppeteer 渲染；兩層 PDF cache；分散式 lock 防並發重生。

### report-pdf
- **Default branch**: main | **Tech**: Vue 3 + Vite + Tailwind + D3.js | **Type**: frontend
- **本質**: 互動式檢驗報告 viewer + PDF 匯出 UI（50+ 報告類型：Gut Zoomer/Food Sensitivity/Cardio/Hormones/Genetics…）。
- **介面**: hash route `/#/:type/:accessionId`；REST → Vibrant LIS backend；Sentry；Puppeteer 批次渲染。
- **生態角色**: 客戶端報告呈現層；接 LIS API 資料 → PDF/web；搭 report-pdf-engine 做 serverless 渲染。
- **活躍度**: Active(2026-05-28)；~649 source files。**Notable**: 支援 VA/VW 多品牌；pdf-merger-js 合併；Element Plus。

### report-pdf-engine
- **Default branch**: main | **Tech**: Node 22 ESM + Fastify + Puppeteer | **Type**: rendering-engine
- **本質**: headless URL→PDF 渲染服務（browser pool），把任意 URL(尤其 SPA) 轉印刷級 PDF + 自動書籤。
- **介面**: `GET/POST /pdf`、`GET /health`、CORS for portal、K8s readiness。
- **資料**: 無(ephemeral Chromium)。
- **生態角色**: 後端渲染基礎設施；被 report-pdf SPA 呼叫產 PDF；也服務其他 portal。
- **活躍度**: Active(2026-06-05)；6 source files。**Notable**: per-request incognito context 防狀態外洩；記憶體 2Gi→4Gi；K8s shm mount。

---

## 4. 通知 / 分析 / 事件 (Notification, Analytics, Eventing)

### LIS-notification-center
- **Default branch**: **master** | **Tech**: NestJS 10.3 | **Type**: REST + gRPC
- **本質**: email/SMS 派送器（Postmark email + Vonage SMS），Kafka/EventHub 消費，狀態追蹤。
- **介面**: HTTP 3090(`POST /notification/QueryEmailResult`)、gRPC、Kafka(`Notification_Center`→`Notification_Center.back`)、EventHub。
- **資料**: MySQL(Prisma)、Kafka、EventHub、Redis(Bull)。
- **生態角色**: 下游通知 consumer；收 Sample/Shipping 等服務經 Kafka 的訊息；與 `LIS-setting-consumer` 是相關的通知/設定消費模式。
- **活躍度**: Active(~2026-06-04)；4.2K LOC(最小)。**Notable**: 近期修 EventHub double-encoded 訊息。

### LIS-backend-dashboard
- **Default branch**: main | **Tech**: NestJS 10 + Prisma 5.22 + ClickHouse | **Type**: gRPC + REST + Kafka consumer
- **本質**: 事件聚合 dashboard — 經 Kafka 收 report/shipping/billing 事件寫 ClickHouse 分析庫。
- **介面**: HTTP 3005(REST/Swagger)、gRPC 5800、Kafka consumer。
- **資料**: ClickHouse(events)、Prisma(optional)、Redis、Kafka。
- **生態角色**: 分析/telemetry 層；全系統活動 event sink；提供 gRPC 給前端 dashboard。
- **活躍度**: Active(2026-05-28)；51 files。**Notable**: 依環境選 Event Hub vs Kafka；OpenTelemetry。

### feature_dashboard
- **Default branch**: main | **Tech**: Python ETL + vanilla HTML/CSS/JS | **Type**: dashboard
- **本質**: 內部 BI dashboard 平台 — ETL 從 ClickHouse 抽到 Supabase Postgres，前端經 Supabase RPC + RLS 取數。
- **介面**: 靜態前端(Netlify)；後端 Python ETL + Supabase RPC。
- **資料**: Supabase Postgres(RLS)、Supabase Auth。
- **活躍度**: Active(2026-06-05)；~12 前端檔。**Notable**: 追蹤促銷成效/PNS portal 指標/報告瀏覽；MIGRATION_PLAYBOOK 教新增 dashboard。

### Message-clone
- **Default branch**: main | **Tech**: Go(kafka-go, Azure SDK, ClickHouse) | **Type**: library/CLI consumer
- **本質**: Kafka→ClickHouse 串流 consumer，把可設定 topic 的事件落 ClickHouse 供存檔/分析。
- **介面**: Kafka/EventHub/ServiceBus(YAML 設定 protocol+auth)；ClickHouse insert；CLI-only。
- **活躍度**: Active(最後 2025-06-30)；4 .go files。**Notable**: 三種傳輸協定；raw(auto-DDL)/legacy 兩種 table；dry-run；`FINAL` 去重。

---

## 5. 認證 / 授權 (Auth & Access — 橫切中樞)

### OAuth
- **Default branch**: main | **Tech**: **Rust** (Axum 0.8 + SeaORM) | **Type**: auth server
- **本質**: 企業級 OAuth 2.0 authz server（authorization code / client credentials / refresh / device flow RFC8628），JWT 經 Azure Key Vault 簽章，分散式 session。
- **介面**: HTTP `/auth/*` `/sessions/*`；gRPC client → Customer Service；Azure Key Vault(RS256)；Redis；PostgreSQL。
- **資料**: PostgreSQL(users/clients/codes/tokens/sessions/login history)、Redis(session/token cache 8h TTL)、Azure Key Vault。
- **生態角色**: **中央認證/授權樞紐**；各服務靠 OAuth token 取身分/claims；session 失效經 Event Hub 跨 pod fan-out。
- **活躍度**: Active(2026-05-28)；83 .rs files。**Notable**: device flow(XXXX-XXXX 5min)；refresh token rotation；3 層 session cache(moka→Redis→Postgres)。

### Vibrant-RBAC
- **Default branch**: main | **Tech**: Go 1.24 (go-micro v4 + Casbin + Ent) | **Type**: rbac service
- **本質**: 中央化 RBAC 微服務，用 Casbin 跨 internal/external/clinic 角色強制權限。
- **介面**: gRPC(go-micro)；gRPC health；Redis；Azure App Config + Key Vault；Event Hub(cache 失效)。
- **資料**: MySQL(rbac_roles/resources/actions + Casbin policy via ent-adapter)、Redis(6h TTL)、in-mem Ristretto(60s)。
- **生態角色**: **權限仲裁中樞**；守所有微服務的 resource 存取；用 `ALLOWED_SERVICES` allowlist 驗呼叫端。
- **活躍度**: Active(2026-06-05)；67 .go files。**Notable**: Casbin RBAC+domains；多層 cache + Event Hub fan-out；Datadog Orchestrion。

---

## 6. 整合 / 資料契約 / 臨床 (Integration, Data, Clinical)

### tcp-di
- **Default branch**: **master** | **Tech**: Node.js (kafka-node/kafkajs + Sequelize) | **Type**: integration gateway
- **本質**: 即時 **ASTM LIS2-A2** 協定閘道 — 從臨床儀器(Roche analyzer 等)收檢驗結果/上樣事件，經 TCP/ASTM → Kafka → MySQL。
- **介面**: **TCP 3000**(儀器訊息)；Kafka(`192.168.60.9:9095` topic `DImessage`)；MySQL(`operation_data` `192.168.60.4:3307`)。
- **資料**: MySQL(roche_loaded_sample / roche_exception_tests)、Kafka(DImessage)。
- **生態角色**: **儀器資料 ingest 層**；橋接臨床裝置到 lab operations DB；餵即時 sample 追蹤/例外管理。
- **活躍度**: Active(2026-05-28)；4 .js files。⚠️ **Notable**: config(broker/MySQL cred/port) **硬編碼未外部化**；Sentry DSN embedded；C6000→R1、AU5800→A1 儀器映射。

### dataContracts
- **Default branch**: main | **Tech**: YAML + Python(datacontract-cli + Great Expectations) | **Type**: data-contract/schema registry
- **本質**: 正式版控的 data contract（Open Data Contract Standard v3）— 定義 schema、品質 SLA、治理、producer/consumer 協議，跨 ClickHouse 與 MySQL。
- **介面**: datacontract-cli 驗證；Great Expectations 對 ClickHouse(`192.168.62.85`/`192.168.10.212`) + MySQL(azure/`192.168.60.2`/`192.168.60.4`) 跑 live 檢查。
- **生態角色**: **共用 schema registry + 治理層**；ETL producer 與 consumer 的約定；防 breaking change。
- **活躍度**: Active(2026-05-26)；57 檔。**Notable**: 同一 logical dataset 多 physical source = 多份 contract(檔名加 server suffix: clickhouse6285/mysql_azure/mysql602/mysql604)；semver 強制。

### encounterNotes
- **Default branch**: main | **Tech**: Python 3.11+ FastAPI | **Type**: backend-service
- **本質**: 醫療 encounter 轉錄 + AI 摘要 + 語意搜尋 — 收醫病音訊，Azure OpenAI Whisper 轉錄，GPT-5/Claude 產 SOAP 摘要，pgvector 向量搜尋。
- **介面**: REST `/api/v1/recording/*`；SSE `/api/v1/transcription/stream/{id}`；Swagger/ReDoc。
- **資料**: PostgreSQL 16(雙 schema: encounter_notes + transcription_vectors HNSW)、Redis 7 Sentinel、Cloudflare R2(音訊)。
- **生態角色**: 臨床文件模組；經 encounter_id FK 接主 EHR；multi-tenant(clinic_id 隔離)；醫師專用。
- **活躍度**: Active(2026-03-19)；~74 Python files。**Notable**: AES-256 + RSA-2048 混合加密 PHI；PG LIST partition by clinic_id；HIPAA audit log；附 TS SDK。

---

## 7. 前端 / Portal (Frontend & Portals)

> ⚠️ 前端 repo `.env`/打包設定常誤含 secret — 改動前注意（見 SECURITY-RISK-URLS 稽核）。

### vibrant-wellness-portal
- **Default branch**: main | **Tech**: Vue 3.3 + Vite 4 | **Type**: portal（診所/內部 admin）
- **本質**: Vibrant Wellness 診所夥伴的 admin portal — announcement/coupon/lab test 設定/臨床排程/webinar/science 內容/AI chat。
- **介面**: dev 5173；消費 Transaction Service GraphQL、Rocket.Chat。
- **生態角色**: 診所端 portal；內容管理 + order routing + practice 整合設定。
- **活躍度**: Active(2026-05-21)；~179 files。**Notable**: Vuex + GraphQL(Apollo)；Userpilot + FullStory；用 pns-component-library + va-responsive-components-library。

### ehr-frontend
- **Default branch**: main | **Tech**: Vue 3.2 + Vue CLI 5(Webpack) | **Type**: portal（provider/診所）
- **本質**: provider 端 EHR portal — 患者管理、即時訊息、預約排程、臨床 workflow(workbench/pegboard/practice)。
- **介面**: dev 8080；消費 Patient API、Rocket.Chat WebSocket(DDP)、EHR Rooms API、Patient Order Service、GraphQL(行事曆)。
- **生態角色**: 主要 provider/診所介面；管理 active 患者、即時溝通、預約、臨床 workflow。
- **活躍度**: Active(2026-06-03)；**~1038 files(最大前端)**。**Notable**: 三欄佈局(患者列|chat|pegboard)；Vue Flow workflow；TipTap 編輯器。

### PNS-Singlepage
- **Default branch**: main | **Tech**: Vue 3.2 + Vue CLI 5 | **Type**: frontend（患者）
- **本質**: 患者端 single-page 訂單後流程 — 付款、問卷、出貨/採檢、抽血排程、專科問卷、預約確認/取消。
- **介面**: dev 8080；消費 Billing/Charge/Order/Patient/Questionnaire/NY Form/CoreSample/Payout/Pricing REST + EMR Calendar GraphQL。
- **生態角色**: **關鍵患者 onboarding/履約 portal**；從 email/portal link 帶患者走完付款→資料→排程才能處理 sample。
- **活躍度**: Active(2026-06-01)；~164 files。**Notable**: Pinia 一 domain 一 store；JWT in localStorage；BNPL(Klarna/AfterPay/Splitit)；Sentry+FullStory。

### pns-portal
- **Default branch**: main | **Tech**: Vue 3.4 + Vite 5 | **Type**: portal（患者）
- **本質**: 患者端訂單追蹤/sample 導覽 portal — 管理訂單、追蹤 kit、看帳單、存取報告、帳號設定。
- **介面**: dev 8000(hash route)；消費 Billing/Order/Transaction/Sample/CoreSample/Inventory/Report/Statement REST + GraphQL(auth)。
- **生態角色**: 購買後主要患者 portal；自助查訂單/帳單/結果。
- **活躍度**: Active(2026-06-01)；~76 files。**Notable**: i18n 英/西；2FA(FingerprintJS)；Zendesk chat；Sentry+FullStory。
- ⚠️ PNS-Singlepage(履約流程) vs pns-portal(訂單追蹤) — 兩個不同患者前端，別搞混。

### va-responsive-components-library
- **Default branch**: main | **Tech**: Vue 3 (TS) + Vite | **Type**: library
- **本質**: 可重用 UI 元件庫(32+ 元件)，供 Vibrant Wellness EHR 系前端共用。
- **介面**: npm scoped `@vibrant-wellness/va-responsive-components-library`；發到內部 registry(`192.168.60.11:8124`) + public npm。
- **生態角色**: 前端基礎層；被 EHR portal / report viewer / 臨床介面消費。
- **活躍度**: Active(2026-06-05)；~84 Vue/TS files。**Notable**: ResponsiveButton 已 deprecated，其餘 production-ready。

---

## 8. Legacy / 汰換中 (Sunset — 改動前先確認是否仍承載流量)

### labsiteAPI
- **Default branch**: **master** | **Tech**: Python Falcon | **Type**: legacy 巨石 backend
- **本質**: legacy 巨石 API(~89K LOC) — lab order/shipping(FedEx)/CRM(HubSpot)/gRPC(sales territory, sample routing)/Celery。
- **介面**: Falcon REST 7999；gRPC；Celery；Kafka。
- **資料**: MySQL(主)、MongoDB、Redis、Elasticsearch、ClickHouse。
- **活躍度**: **Active but stale**(2026-03-25, 2+ 月)；大量 deprecated/disabled Celery job；舊版套件(SQLAlchemy 1.3/Falcon 1.4/pymongo 3.7)。
- **生態角色**: 仍是核心 order/sample/shipping 營運後端，但逐步被 gRPC 微服務取代。

### LIS-backend-billing
- **Default branch**: **master** | **Tech**: Java 8 / Spring Boot 2.5 + MyBatis | **Type**: REST + gRPC + 排程
- **本質**: 帳務(order 處理/payment 追蹤/charge/receipt/discount)，被 v2-billing 取代中。
- **介面**: HTTP 4242(Swagger)、gRPC 8111。
- **資料**: MySQL(Druid)、Redis Sentinel、Kafka+RocketMQ(optional)。
- **活躍度**: Active(2026-06-02)；838 Java files。**Notable**: ShedLock/Redis 分散式鎖；Spring 啟動後才起 gRPC。

### LIS-backend-statement
- **Default branch**: main | **Tech**: Python 3.11 Falcon ASGI + aiohttp | **Type**: 聚合 gateway
- **本質**: 財務 statement 產生/查詢 — 從 core/order/accounting 聚合多實體視圖（read-only，無業務資料儲存）。
- **介面**: HTTP 8084(4 uvicorn worker)。
- **資料**: Redis Sentinel(僅 cache)、gRPC→core、HTTP→order/accounting、外部 PDF engine。
- **活躍度**: Active(2026-05-20)；~50 files；V2-V6 多版本端點；**流量正遷往 v2 服務**。

### LIS-accounting-wsgi
- **Default branch**: main | **Tech**: Python 3.11 — Falcon WSGI + FastAPI ASGI(依環境選) | **Type**: legacy 帳務
- **本質**: legacy 帳務服務，**標 "RETIRE FOR GOOD"**，流量遷往 v2。
- **介面**: HTTP 8084(dual-stack)；gRPC client(非 server)。
- **活躍度**: **Sunset/maintenance**(2026-06-03)；50 files；**僅 discount 端點仍有 production 流量**，invoice/statement 已遷走。
- **Notable**: AppEnv 決定 framework(on-prem prod/staging 用 Falcon WSGI、cloud/local 用 FastAPI)；gRPC metadata service-name="lis-accounting"。

---

## 9. QA / 測試

### TestRepo
- **Default branch**: main | **Tech**: Node + TS (Playwright + Postmark SDK) | **Type**: E2E 測試套件（**非服務**）
- **本質**: Vibrant America portal 的 E2E/QA 套件 — Playwright 自動化(smoke/regression/deep/API/perf)。
- **介面**: CLI-only；Playwright runner；Xray reporter→Jira；Postmark(email invite 驗證)。
- **活躍度**: Active(2026-06-05)；**462 .ts/.js files、~686MB**(含大量 Playwright report)；126 merged PR。
- **Notable**: 不是 service/library，是正式 QA harness；近期 75→27 smoke test 整併、修 14 regression flake。

---

## 速查表 (Quick Index)

| Repo | 語言 | 類型 | branch | 一句話 |
|------|------|------|--------|--------|
| LIS-backend-v2-order-management | Go | μservice | main | 訂單生命週期中樞 |
| LIS-backend-v2-billing | Go | μservice | main | invoice/結算/credit |
| LIS-backend-v2-charging | Go | μservice | main | 收款閘道(Stripe/Stax) |
| LIS-backend-v2-payout | Go | μservice | main | 撥款給診所/抽血師 |
| LIS-backend-v2-pricing | Go | μservice | main | 定價/促銷引擎 |
| LIS-backend-coreSamples | NestJS | REST+gRPC | main | 核心 sample/patient(NestJS) |
| LIS-Sample | NestJS | REST+gRPC | master | sample order/tube 庫存 |
| LIS-Shipping | NestJS | REST+gRPC+WS | master | 物流/出貨/carrier |
| LIS-Lab-test | Go | gRPC | main | test catalog/range 權威源 |
| LIS-Report | NestJS | REST | main | PDF 報告產生/版控 |
| report-pdf | Vue | frontend | main | 報告 viewer+PDF UI |
| report-pdf-engine | Node Fastify | engine | main | URL→PDF 渲染(Puppeteer) |
| LIS-notification-center | NestJS | REST+gRPC | master | email/SMS 派送 |
| LIS-backend-dashboard | NestJS | gRPC+Kafka | main | 事件→ClickHouse 分析 |
| feature_dashboard | Py+JS | dashboard | main | 內部 BI(Supabase) |
| Message-clone | Go | CLI consumer | main | Kafka→ClickHouse 落地 |
| OAuth | Rust | auth | main | OAuth2 authz 中樞 |
| Vibrant-RBAC | Go | rbac | main | Casbin 權限仲裁 |
| tcp-di | Node | integration | master | 儀器 ASTM→Kafka→MySQL |
| dataContracts | YAML+Py | schema registry | main | data contract 治理 |
| encounterNotes | Py FastAPI | backend | main | 醫療轉錄+AI 摘要 |
| vibrant-wellness-portal | Vue3/Vite | portal | main | 診所 admin portal |
| ehr-frontend | Vue3/CLI | portal | main | provider EHR portal(最大) |
| PNS-Singlepage | Vue3/CLI | frontend | main | 患者履約流程(付款/問卷) |
| pns-portal | Vue3/Vite | portal | main | 患者訂單追蹤 portal |
| va-responsive-components-library | Vue3 | UI lib | main | 共用 UI 元件 |
| labsiteAPI | Py Falcon | legacy 巨石 | master | 舊 order/shipping(汰換中) |
| LIS-backend-billing | Java Spring | legacy 帳務 | master | 舊帳務(→v2-billing) |
| LIS-backend-statement | Py Falcon | 聚合 gateway | main | statement 聚合(→v2) |
| LIS-accounting-wsgi | Py | legacy 帳務 | main | RETIRE，僅 discount 仍用 |
| TestRepo | Playwright | QA(非服務) | main | E2E 自動化測試 |

> 已在 `repos.md` 詳載的活躍開發 repo（LIS-transformer / -v2 / lis-backend-emr-v2 / LIS-backend-v2-coreSamples / EMR-Backend / results-grpc / results-core / setting-consumer）此處不重複，深度 gotcha 看 `repos.md`。
