---
id: patterns
type: ltm
category: repo_patterns
status: active
score: 0.2079
base_weight: 0.8
created: 2026-04-22
updated: 2026-07-22
links:
- INCIDENT-20260528
- INCIDENT-20260529
- INCIDENT-20260601-sftp-hang
- VP-15460
- VP-16175
- VP-16193
- VP-16232
- VP-16245
- VP-16251
- VP-16329
- VP-16361
- VP-16410
- VP-16424
- VP-16476
- VP-16720
- VP-16784-87
- VP-17407
- VP-17408
- VP-17653
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

### VA Jira：關閉 Bug 前必填 Root Cause + Root Cause Category（VP-16954 教訓）
- VA Jira 的 **Bug** issue 要走到 **Done**（transition id=15）會被 issue-level validator 擋：**"Root Cause and Root Cause Category must be completed before closing this bug."**
- 這兩個欄位**不在** Done 的 transition screen（`hasScreen=false`），也**不在**當前狀態的 `editmeta` / `transition.fields` 暴露 → 用 MCP `transitionJiraIssue` 直接打會失敗、且抓不到 field id。
- 要關 VP Bug 前：先用 `editJiraIssue` 備妥 Root Cause + Root Cause Category 兩欄（或請 Leo 在 UI 填），再 transition。非 Bug 類型（Task/Story）無此限制。
- **Field ids（VP-17342 實測 2026-07-09）**：`customfield_10485` = Root Cause（rich text）、`customfield_10490` = Root Cause Category，選項 7 種：Code Defect / Configuration Error / Infrastructure / Process / Dependency / Requirements-Design / Insufficient Testing。
- 找這類 field 用 `getJiraIssueTypeMetaWithFields`——VP Bug 的回應約 **217k chars**，要存檔再 parse；MCP 會把 SSE deprecation notice prepend 在 JSON **前面** → `json.loads(blob[blob.find('{'):])`。

### class-validator `@IsOptional` 不跳過空字串（VP-16955 教訓）
- `@IsOptional()` **只**在值為 `null` / `undefined` 時跳過後續驗證；空字串 `""` 視為「有提供值」仍會跑 `@Length` / `@Matches` 等 → 前端送 `field: ""` 會炸 400。
- 修法（最小改動）：欄位加 `@Transform(({ value }) => typeof value === 'string' && value.trim() === '' ? undefined : value)`（class-transformer，NestJS ValidationPipe 在 plainToInstance 階段即執行，驗證前生效），非空值仍受格式驗證保護。
- 條件式驗證（某 vendor/type 才必填）若判斷依據需查 DB（DTO 只有 id），**不要**在 DTO 塞 async custom validator——留在已載入該 record 的 service 層，DTO 只負責放行空值。

### NestJS 11 ValidationPipe nested-DTO 錯誤前綴 + scoped 清理只能用 filter（VP-17077）
- NestJS 11 預設 ValidationPipe 對 `@ValidateNested()` 子 DTO 的錯誤訊息會**加 property-path 前綴**，例如 `clinicInfo.Customer NPI must be exactly 10 digits`（top-level 欄位無前綴）。回傳 body 為 `{statusCode, message: string[], error}`。前端若把 `message` 陣列原樣 render 會變 `{"..."}`（那是前端問題，非後端）。
- **要 scoped（單 controller）清掉前綴：用 controller-scoped exception filter（`@Catch(BadRequestException)` + `@UseFilters`），不要用 scoped `ValidationPipe`+`exceptionFactory`**——因為全域 ValidationPipe（main.ts）**先**跑先 throw，route/controller 級的 pipe 永遠輪不到。filter 才攔得到全域 pipe 丟的例外。範例 `integration-management/auto-integrate/filters/validation-error-cleanup.filter.ts`：strip `^(?:[A-Za-z_$][\w$]*\.)+`，非陣列 message / 一般 BadRequest 原樣放行、保留 response shape。
- 驗證這類「filter 是否攔到 global pipe 例外」務必用 **HTTP 整合測試**（`Test.createNestApplication` + `app.useGlobalPipes(同 main.ts)` + supertest），單元測 filter 邏輯不足以證明攔截鏈。`supertest` 用 `import * as request`；spec 命名 `.spec.ts`（`.e2e-spec.ts` 不被預設 jest config 收）。

### Environment Variables
- 各專案用不同的 env var 名稱：`NODE_ENV` / `SERVER_ENVIRONMENT` / `DEPLOY_ENVIRONMENT` / `platform_type`

### gRPC from Standalone Scripts
- NestJS `createApplicationContext` 不初始化 gRPC `@Client` decorator — migration script 無法透過 NestJS DI 取得 gRPC service
- 解法：用 `@grpc/grpc-js` + `@grpc/proto-loader` 直接建 client 連 `192.168.60.6:30276`（見 `emr-integration.md`）
- 需要 OAuth2 metadata: `authorization` (Bearer), `x-request-id`, `internal-user-id`, `service-name`
- OAuth2 token: client_credentials grant，env vars `OAUTH2_CLIENT_ID` / `OAUTH2_CLIENT_SECRET` / `OAUTH2_TOKEN_ENDPOINT`
- `.env` 裡 `CORE_SAMPLE_V2_RPC` 是 cluster DNS（`...svc.cluster.local:8084`），只在 cluster 內可達
- **VPN 開時** `192.168.60.6:30276`（v1）跟 `10.224.0.199:32100`（v2 coreSamples）兩個內網 IP 從本機都可達，可直接跑 verify script — 用 IP 不要用 cluster DNS

### lis-backend-emr-v2 雙 proto 樹
v1 跟 v2 的 RPC 各有獨立 proto 檔，**改 RPC 前先看 `src/config/grpc.config.ts` 對應的 path**，避免改錯邊：

| 路徑 | proto package | host (default) | upstream service |
|------|---------------|----------------|------------------|
| `src/proto/*.proto` + `dist/proto/*.proto`（兩份要同步）| `lis` | `192.168.60.6:30276` | legacy LIS / lis-pkg |
| `src/proto-v2/*.proto`（單一份，無 dist 鏡像）| `coresamples_service` | `10.224.0.199:32100` | `LIS-backend-v2-coreSamples`（Go）|

判斷規則：upstream 在 coreSamples Go repo（`package coresamples_service`）→ 改 proto-v2；upstream 在 LIS-transformer 系列 → 改 proto。
v2 client wrapper 在 `src/modules/grpc/services/grpc-client-v2.service.ts`（`getCustomer` / `getCustomerByNPINumber` / `getClinicIDsByNPINumber` 等）。新 RPC method 仿既有 pattern：deadline + metadata + `client.RpcName(req, metadata, {deadline}, cb)`，輸入用 snake_case key 對應 proto field。

### Port 既有系統時必查 v1 deployment yaml（VP-16463 教訓）
做 Java → TS / 任何「改寫既有 production 系統」的 port，**第一步要讀 v1 的 K8s/deployment/docker 設定**，不只看 application code。要逐項列出並在 v2 對應：
1. **Filesystem paths**：v1 寫到哪？env var 名是什麼？路徑是不是掛在 PVC 上？
2. **Volume mounts**：用了什麼 PVC、storageClass、accessMode？hostPath PV 會強制 nodeName pin
3. **env vars**：v1 deployment 設了哪些 env？v2 ConfigMap 是不是有對應？
4. **Replicas / nodeName**：v1 是不是有特殊放置策略（hostPath 一定要 pin）

VP-16463 我只看 Java code，沒看 `EMR-Backend/deployment_prod.yml`，結果 v2 預設 `/tmp/hl7` 是 pod ephemeral：fetch service 下載成功立刻 `deleteFile(remotePath)` 把 SFTP 端刪掉，pod 重啟（每次 deploy 必發生）`/tmp` 連根帶葉清空 → 檔案永久失蹤、SFTP 也沒了。Recovery 只能等 vendor 重送。

**衍生規則 - `default` / `fallback` 值**：任何 `config.get('X', 'fallback')` 寫法都要自問「這 fallback 在 prod 被觸發會發生什麼？」`/tmp` 對任何 prod 系統都不是合理 fallback。
**衍生規則 - 上游刪除時機**：任何「下載 → 刪上游 → 處理本地」flow，刪上游必須延後到「處理完成且資料持久化」之後，否則中途崩潰 = 資料雙失。

### 改 K8s yaml 前必先 `kubectl diff` 確認 repo ≠ cluster drift（VP-16463 教訓）
任何 `kubectl apply -f repo.yaml` 之前**必須**：
1. `kubectl get deployment/svc/configmap X -o yaml > /tmp/cluster.yaml`
2. `diff /tmp/cluster.yaml repo.yaml` 比對
3. 對每個欄位確認「以誰為準」— 不要假設 repo 是 source of truth

VP-16463 我假設 repo yaml 是對的、直接改 image registry 從 internal 改成 Azure ACR、apply 後 cluster 拉不到 image → ImagePullBackOff、rollout 卡死、PVC mount 跟著沒生效、生產差點斷線。

實際 drift 來源：
- 早期計畫 deploy 到 Azure AKS、yaml 寫 Azure ACR image
- 後來改 on-prem 部署、image 改 push 到內網 `192.168.60.10:6004/vibrant/`
- 沒人同步更新 repo yaml
- Jenkins 還會從 Azure AKS 抓 ConfigMap 蓋到內網 cluster（即 ConfigMap source of truth = Azure 那邊，不是 repo）

**衍生規則 - CI/CD 完整鏈路必須先理清**：改 deployment yaml 前要釐清：
1. 哪個 branch push 觸發 build？
2. Build 用什麼 tag/registry？
3. Cluster 從哪個 registry 拉？有 imagePullSecret 嗎？
4. ConfigMap source-of-truth 在哪？（repo / 另一個 cluster / 手動編輯？）
5. Deployment yaml 自動 apply 嗎還要手動？

**衍生規則 - 多 namespace audit**：debug 前先 `kubectl get pods -A | grep <app>` 列出所有 namespace 的同 image pod。VP-16463 揭發 staging-ns 殭屍 pod 跑 13 天每 5 分鐘 CrashLoopBackOff、偷下載檔案後 wipe、隱藏 data loss。

### Azure 帳號看不到資源 ≠ 公司沒這個資源（PO-222 教訓）
hung.l@zymebalanz.com 只看得到 `Subscription 1`（id `4dbf30e2-...`），裡面只有 AKS + Event Hub，**找不到 Azure Cache for Redis**。但 prod `vibrant-cloud-cache.redis.cache.windows.net` 確實存在 — 它在另一個 subscription，Leo 帳號無 RBAC，但 in-cluster pod 用 hostname DNS 解析照樣連得到。

**衍生規則 — 找連線資訊的正確順序**：
1. 別只看 `az resource list`（受 RBAC 限制）
2. 看跑在 prod AKS 裡的 pod env：`kubectl -n <ns> get cm <service>-config -o yaml | grep -i <resource>` 拿 host/port
3. `kubectl -n <ns> get secret <service>-secret -o jsonpath='{.data.<KEY>}' | base64 -d` 拿密碼
4. 連線方式：起 ephemeral pod `kubectl run -it --rm --image=redis:7 ... -- redis-cli`，密碼用 `REDISCLI_AUTH` env 不要塞 `-a` argv

### LIS prod / staging Redis 連線地圖（PO-222 盤點）
| 環境 | Host | Port | 類型 |
|---|---|---|---|
| Prod | `vibrant-cloud-cache.redis.cache.windows.net` | 6380 TLS | Azure Cache for Redis (Standard) |
| Staging | `lis-cache.westus3.redis.azure.net` | 10000 TLS | Azure Managed Redis (Enterprise) |
| Legacy on-prem (prod) | `192.168.60.9-11` | 26390 | Sentinel — 3/22 後應停用 |
| Legacy on-prem (staging) | `192.168.10.121/98/80` | 26390 | Sentinel |

Password secret key: `REDIS_VIBRANT_CLOUD_CACHE_PASSWORD`（在 `lis-test-rpc-secret` / `lis-test-rpc-staging-secret`）。AKS context: `lisportalprod`。

### ⚠ Known issue：prod transv2 的 redis user 對 vibrant-cloud-cache 是 NOPERM（VP-17422, 2026-07-16 實測）
在 prod transv2 pod 內跑 `/dist/redis.js getRedisClient()`：連線成功（6380 db0），但**每一個 op 都丟 `NOPERM this user has no permissions to access one of the keys`**——連 bare key `x`、`ACL WHOAMI` 都不行，該 user 有零 key 權限。後果：**prod transv2 任何 redis-based coordination（lock、cache、dedup）都靜默失效**，不只 daily report；且 LisLoggingService log 進 Datadog 不進 stdout，pod log 看不到。Infra fix（未做，無 RBAC）：grant prod transv2 MI objectId `754903bb-f6e2-4994-a7d9-dca2c3d516ef` 一個 Data Access Policy on vibrant-cloud-cache。在此之前：transv2 prod 需要跨 replica 協調 → 用 calendar DB（unique-INSERT claim / advisory lock），不要碰 redis。

### Per-pod Redis sidecar + Redlock 無法跨 pod 同步（VP-16463 教訓）
Pattern：deployment 用 sidecar container 跑 Redis（`REDIS_HOST=localhost`、`emptyDir`），多 replica 時**每 pod 各有獨立 Redis**。Redlock 的鎖只在單 pod 內有效、跨 pod 完全沒同步效果。

VP-16463 撞到：
- staging deployment 2 replicas + prod deployment 1 replica + staging-ns 殭屍 pod = 4 個 pod
- 全部讀同一張 `sftp_folder_mapping` table
- 全部各自跑 fetch cron、各自 acquire Redlock（自己的 Redis 永遠 success）
- 全部試圖下載同一批 SFTP 檔案
- 靠 DB `alreadyIngested(remotePath)` 防重複、但已浪費 SFTP/network/disk

修法：要嘛**外掛共用 Redis**（Azure Cache / 獨立 Redis deployment），要嘛改用 **DB-based lock**（`SELECT ... FOR UPDATE`、advisory lock）。

**衍生規則 - 共用外部資源前先盤點 worker**：任何 worker 寫 DB / 打 SFTP / 呼叫外部 API、deploy 前先列出**全部會 run 這個 cron 的 pod**（多 deployment / 多 namespace / 多 replica）+ 確認 distributed lock 真的能跨 pod。

### Container restart ≠ Pod restart（VP-16463 教訓）
`kubectl get pods` 的 `RESTARTS` 欄位是 **container 重啟次數**，不是 pod 重啟。常見誤判：用戶看「AGE = 17h、RESTARTS = 0」→ 以為 pod 一直好好的、不可能丟 `/tmp` 資料。但實際上：
- **Pod replacement**：rollout restart / scale / node drain → pod name 變、`/tmp` 全新（這個會記在 RESTARTS=0 但 pod AGE 短）
- **Container restart**：liveness probe failure / OOMKill / app crash → pod name **不變**、AGE 不變、但 RESTARTS+1、**`/tmp` 被重建**
- **Node process restart inside container**：少見、PID 1 變、container 不重啟

判斷方式：
```bash
kubectl describe pod $POD | grep -E "Last State|Started:|Exit Code|Reason:"
# Last State Terminated + Reason: OOMKilled → container 重啟過
# Started: 比 pod CreationTimestamp 晚 → container 重啟過
kubectl exec $POD -- ps -eo pid,etimes,cmd | head
# etimes (秒) 比 pod AGE 短 → process 重啟過
```

### `kubectl logs deploy/<name>` 只取樣一個 pod（VP-17474 教訓）
`kubectl logs deploy/...` 只挑 deployment 的**其中一個** pod。多 replica（如 lis-trans prod x3）時用它統計事件（token 發放數、error 數）會**低估 N 倍**。要全量就 iterate pods：`kubectl get pods -l app=<label> -o name | xargs -I{} kubectl logs {}`，或用 `--prefix -l <selector>` 直接對 label 取 logs。統計型驗證（「有幾筆」）一律先確認 replica 數。

### Java → TS port 的硬性 parity rules（VP-16463 教訓）
任何 v2-port over v1 Java 的 service：
1. **Terminal states 必須 set `parse_finished=true`**（或同等 finished flag）— 否則 BullMQ / 工作 queue 不停 retry terminal error。Java parser 對 `customer_not_found` / `emr_code_not_found` 都 set parse_finished=1 + return。VP-16463 v2 沒設 → retry 5 次 + 浪費 cycle
2. **不要加 v1 沒有的前置 gate**：VP-16463 v2 在 Stage 3a 加了 NPI hard-gate，當 ORC.12.1 不是純數字就 reject、用 `NO_NPI` 標 customer_not_found。Java 沒這個 gate，把所有 customer lookup 留給 parser 內的 `order_clients` 查詢。**Pre-gate = parity 破裂的常見原因**
3. **HL7 segment terminator 用 `/\r\n|\r|\n/` 不要假設單一字符**：HL7 spec 是 `\r`、但實際 vendor 用 `\r`、`\r\n`、`\n` 都有。Java HAPI parser 自動處理、v2 手刻 parser 要明示處理。**VP-16463 的 6053/6058 NO_NPI bug 真正 root cause 就是 v2 decoder 用 `.split("\r")` 但 vendor 送 `\n`-only → segment 沒拆出來 → ORC 找不到 → NPI 為空 → NO_NPI**
4. **OML→ORM normalize**：Java `HL7_package.normalizeIncomingMessageType` 把 OML^O21 改寫成 ORM^O01 給 Practice Fusion 等 vendor 用。v2 port 不能漏這層、否則 OML vendor 全爆
5. **Java Gson 對 null field 預設 omit、TS JSON.stringify 不 omit**：構造 OrderFrontend 等 JSON 時、null 欄位要**條件設值**而不是 unconditional set null，否則跟 Java 序列化結果不一致
6. **Java `HashSet<T>` 順序未定、TS `Array` 插入順序保證**：用 Set 累積 testIdList 之類的、轉換時要記得 Java 端順序不保證、v2 用 Array 可能造成 BestDeal input 排序差異

### Prod GraphQL endpoint 測試 = 不可逆 fire-and-forget 副作用（VP-16410 教訓）
不要用 Postman 打 prod URL（如 `api.vibrant-america.com/v2/portal/trans-service/graphql`）測新 mutation，即使「事後手動刪 row」也救不回 downstream：
- `createEvent*` 觸發 `appointmentEventService.sendAppointmentEvent(...)` → publish 到 Kafka topic `general-sample-events`，下游消費者已處理
- `sendAppointmentScheduledEmailFor*` 觸發 publish 到 `notification-email-template` → Postmark 已寄出（clinician / patient 收到假 email）
- 事後 `DELETE FROM v2_event WHERE event_id=X` 只清 DB row，Kafka event + email 撤不回
- **只在 local server 連 dev_new schema 測**，或 deploy 到 staging。手動造假資料用 raw SQL 直接寫 `v2_event_accession_claim` 等內部表模擬狀態，不要透過業務 mutation 創 event

### Prisma `ON DELETE CASCADE` 不會走 service hook → 沒 audit
schema 加 FK `ON DELETE CASCADE` 後，手動 SQL DELETE 父表（如 `v2_event`）會 cascade 清子表 row（`v2_event_accession_claim` 等），但**不觸發 service 的 release 邏輯，不寫 audit log**。要保留 audit 必須走 service mutation（如 `deleteEventByPatient` 而非 raw SQL）。寫 audit 完整性需求時要明白告知 ops 「不要 raw SQL 刪父表」，或在 audit table 設計上獨立追蹤（譬如加 trigger）。

### scripts/ 目錄被 gitignore
`/scripts/` 在 `.gitignore`，但既有 ~1396 個 tracked scripts 是早期 commit 留下來的（規則晚加）。新加的 standalone script 預設不會進 commit — 要 `git add -f` 才能 track。每個 ticket 自行決定 verify/migration script 是否該入 repo。

### EMR-Backend repo root 有大量 untracked junk（git add 危險）
EMR-Backend repo root 本身就有 100+ untracked 雜檔（License 文字、Test*.java、ProcessOrder.java、CheckEnv.java、JAR extracts ca/、com/、common/、javax/ 等、`.class` 編譯產物）。任何寬範圍 `git add .` / `git add src/` 都會打包這些 junk — d8ec891 incident（2026-05）就是這樣產出 34 個檔案 / 10292 行的污染 commit，造成 staging Jenkins build 失敗。
- **避雷**：每次 commit 都 `git add <specific-file>` by name，commit 後立即 `git show --stat HEAD` 確認 staged file count 跟預期一致
- **清理流程**：若髒 commit 已 merge 進 protected branch (staging/production)，從該 branch 開新 cleanup branch，`xargs git rm < <(git show --name-only --format='' <bad-sha>)`，發 PR revert junk 但保留同 PR 內合法的 commit（不要直接 revert merge commit，會連同合法改動一起 revert）

### scripts/ 內 .ts 會破壞 nest build dist 扁平結構（VP-16410 incident）
LIS-transformer-v2 等 NestJS repo 的 `tsconfig.build.json` 預設沒 exclude `scripts/`，所以在 repo root `scripts/` 寫 `.ts` 檔，tsc 會把 `scripts/*.ts` 跟 `src/*.ts` 同時 include。為避免 output 衝突，dist 結構從**扁平**的 `dist/main.js + dist/trans/...` 變成**嵌套**的 `dist/src/main.js + dist/src/trans/... + dist/scripts/...`。原本以相對路徑 import 外部資源（如 `prisma2.service.ts` 用 `'../../prisma2/generated/client2'`）的解析路徑會差一層，runtime crash with `Cannot find module '...'`。
- **避雷**：repo root scripts/ 內寫 utility 一律用 `.js`（直接呼叫 PrismaClient JS API，不用 ts-node）；要寫 TypeScript 就放 `src/` 之外、或加進 `tsconfig.build.json` 的 `exclude`
- **症狀辨識**：`npm run start:dev` 在 nest build 後 import 失敗，且 `git diff` 為空 → 把搜尋範圍擴到「untracked .ts 檔可能改變 tsc include scope」這條軸；先看 `dist/` 頂層結構（有沒有多/少一層）比 grep import path 更快

### npx tsx 跑 prisma script 必須在 project dir（VP-16424 教訓）
寫在 `/tmp/_*.ts` 的 standalone script 用 `npx tsx /tmp/foo.ts` 跑會找不到 `@prisma/client`，因為 Node module 解析從 cwd 往上找 `node_modules`。改放到 project 內的 `scripts/` 跑，或從 project root `cd` 後執行：`cd lis-backend-emr-v2 && npx tsx /tmp/foo.ts`（仍會走專案的 node_modules）。較乾淨的做法是把 working script 放 `scripts/_<ticket>-*.ts`（gitignore 已涵蓋，不入 commit）。

### Prod 批次 backfill：BEGIN + UPDATE + DO block auto-verify + COMMIT（VP-16713 確立）
小範圍（10~50 筆）prod DB backfill 用 single transaction，搭配 PL/pgSQL DO block 在 COMMIT 前自動 100% verify：

```sql
\set ON_ERROR_STOP on
SET search_path = <target_schema>;
BEGIN;

UPDATE <table> SET <col> = '<val1>' WHERE id IN (...);  -- group 1
UPDATE <table> SET <col> = '<val2>' WHERE id IN (...);  -- group 2

DO $$
DECLARE matched INT; total INT := <N>;
BEGIN
  SELECT COUNT(*) INTO matched FROM (VALUES
    (id1::int, 'expected_val1'), (id2, 'expected_val1'), ...
  ) AS exp(id, expected)
  WHERE EXISTS (SELECT 1 FROM <table> t WHERE t.id = exp.id AND t.<col> = exp.expected);
  IF matched <> total THEN
    RAISE EXCEPTION 'VERIFY FAILED: %/% match', matched, total;
  END IF;
  RAISE NOTICE 'VERIFY OK: %/% match', matched, total;
END $$;

SELECT id, <col> FROM <table> WHERE id IN (...) ORDER BY id;  -- visual confirm
COMMIT;
```

關鍵設計：
- `\set ON_ERROR_STOP on` — 任何錯誤立刻停止，避免 partial COMMIT
- DO block `RAISE EXCEPTION` 會把整個 transaction 推到 abort state → 後續 `COMMIT` 自動退化為 `ROLLBACK`
- expected-value 列表 inline 在 DO block，比 SELECT 後手動比對更可靠（防止人眼看錯）
- 對齊 feedback_batch_db_verify：100% 驗證，不 spot check

適用場景：手動 backfill / 小規模 cleanup（10~50 筆）。全表級 UPDATE（>1000 筆）改用下節 prisma.$transaction interactive。

### prisma.$transaction interactive 全表 UPDATE 要拉 timeout（VP-16476）
`prisma.$transaction(async (tx) => { ... })` interactive transaction 預設 timeout 5s，全表級 UPDATE（如 1000+ row 的 backfill）容易 timeout 並 rollback。寫法：
```ts
await prisma.$transaction(async (tx) => {
  // pre-check sanity guard
  await tx.$executeRawUnsafe(`UPDATE ... `);
  // post-check
}, { timeout: 60_000 });
```
60s 對 1000~5000 row UPDATE 通常足夠；更大規模考慮拆批或單獨 raw SQL（不在 tx 中）。

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

### Manual-DDL + auto-deploy-on-merge：merge 即事故窗（VP-17474 教訓，2026-07-22）
LIS-transformer / LIS-setting-consumer 是 **push 即 deploy**（GitHub Actions：push `stage_test` → staging AKS，push `main` → prod AKS），而 DB schema 是手動 DDL（prod lisportalprod2 / staging 192.168.60.11 皆非 Prisma-managed）。
- VP-17474 事故：code 需要新欄位 `recipient_clinic_id`，PR merge 到 stage_test 後幾分鐘內 promotion PR（標題「Stage test」、不帶 ticket id，`gh pr list --search "VP-xxxx"` 找不到）就上了 main → prod 跑新 code 但欄位不存在 → token issuance 全掛 20h（silent-failure #9）。
- 紀律：**DDL 先於 merge，不是先於 deploy** — 在 auto-deploy repo，merge 就是 deploy。staging + prod 兩邊 DDL 都 confirm 後才 approve/merge；或 PR 描述明寫「merge 前提 = DDL applied both envs」。
- 對照組（同週正確做法）：BIOINSIGHTS/emr-v2 — migration 先 apply 到兩 DB、驗證 old-code 讀取無恙（DB ahead of code = safe direction）後才 merge。
- 找 promotion PR 別只 `--search` ticket id — 用 merge 時間窗 + base branch 過濾。

### mysql2 Timezone
- **每個 DB 的 datetime 慣例不同，連線前先確認 — 別假設都是 UTC**：
- Legacy MySQL（lis_core 系）datetime 存 UTC 無 timezone info → mysql2 必須加 `timezone: '+00:00'`，否則用本機時區解讀導致偏移
- `lisportalprod2`（lis_frontend_service / lis_emr）**實測 `@@time_zone = +00:00`，`NOW()` = UTC**（2026-07-22 dream closeout audit：`NOW()` 與 `UTC_TIMESTAMP()` 相同、`MAX(created_at)` 吻合 UTC wall clock）。VP-17474 工作中曾誤判「DATETIME 存 PDT / NOW() 是 PDT」並據此寫 verify — 教訓：**寫時間過濾前先 `SELECT @@session.time_zone, NOW(), UTC_TIMESTAMP()` 對表**，用 `dateStrings: true` 拿 raw 字串（別讓 mysql2 的 JS Date 本機時區轉換替你翻譯），且時間戳斷言要對上一個已知 wall-clock 事件才可信

### DB UPDATE transaction 加 pre-check sanity guard
對 prod DB 跑 UPDATE/INSERT 前，在同一 script 先 SELECT 當前狀態並比對預期值（e.g. `integration_type === 'RESULT_ONLY'`、`emr_name === null`、target row 仍存在）。不符就 throw、阻擋 transaction，避免 STM/分析跟 DB 真實狀態之間的時間差導致誤改。配合 `prisma.$transaction` rollback 可全套保護。範例：VP-16396 的 `_apply-vp16396.ts` 在 ehr_integrations / order_clients / sftp_folder_mapping 三表分別 SELECT 比對後才執行兩條 UPDATE。

### 複雜 service method 的 auth-path unit test
測試一個會觸發大量 downstream 邏輯的 service method 的授權前段時，用 `jest.spyOn(service as any, '<downstream-private-method>').mockResolvedValue(...)` 短路後續流程，只跑授權檢查再立即 return。避免 mock 整條 pipeline（prisma transactions、kafka publish、email service…）。範例：LIS-transformer-v2 的 `updateEventByPatient` 測試 spy `updateWholeEventRecord` / `mapEventToGraphQL` / `buildWholeEventUpdateData` / `resolveRecurringEditScope`，使 happy-path 測試短小可讀（VP-16361）。

### order_clients 無 updated_at 欄位
`lis_emr.order_clients` schema **沒有 `updated_at` 欄位**（不像 `ehr_integrations` 有）。寫 raw `UPDATE order_clients SET ... updated_at=NOW()` 會 fail with `Unknown column 'updated_at' in 'field list'`。寫 SQL 前先驗 schema，或避開 updated_at。完整欄位：id, customer_name, customer_id, customer_provider_NPI, customer_practice_name, clinic_id, kits_options, emr_name, remote_folder_path, old_clinic_id。

### ehr_integrations.updated_at 不會自動更新 — 不可當「config 何時被改」的證據（2026-08-15 dream closeout audit）
`SHOW COLUMNS FROM ehr_integrations LIKE 'updated_at'` → `datetime / NOT NULL / Default NULL / Extra 空`。
**沒有 `ON UPDATE CURRENT_TIMESTAMP`、沒有 DEFAULT** — 只有應用層或人手在 SET 清單裡明寫才會前進。
VP-17715 的 rollout SQL（`UPDATE ehr_integrations SET result_push_level=..., deferred_report_short_names=...`）
沒帶 `updated_at`，所以 8/14 flip 之後那筆 row 的 `updated_at` 還停在 `2026-07-16 23:26:51`。
夜審時我差點據此判定「flip 根本沒生效」。
- **紀律**：驗 config 變更看**欄位值本身**（`result_push_level='PER_REPORT_GROUP'`），不要看 `updated_at`。
  想留時間軌跡就在 UPDATE 裡明寫 `updated_at = UTC_TIMESTAMP()`。
- 對照 line 320：「有 `updated_at` 欄位」≠「這個欄位被維護」。判斷任何表能不能拿來做時間推論之前先 `SHOW COLUMNS` 看 `Extra`。
- 反例（同 DB 不同表）：`result_transmission_records.updated_at` **會**前進，重播偵測（line 1299）靠的就是它。逐表確認，不要跨表類推。

### "IN (lookup-list) + 取 first row" 必須在同 WHERE 把所有 lookup criteria filter（不要靠 PK ASC 取 first）
模式錯誤：`SELECT * FROM table WHERE id IN (?,?,?)` 然後 caller 取 first row 當作 match — 如果 IN list 含 noise（譬如 NPI gRPC over-return）或 row 的 lookup column 寫錯，PK ASC 會放大 data inconsistency 取錯 row。**修法**：把所有 lookup column 都 filter 進 SQL。
- **EMR-Backend `ParseHL7.fetchCustomerDetailsByNpi` 教訓**：原 SQL 只 `customer_id IN (gRPC NPI lookup result)` 沒驗 `customer_provider_NPI = inputNpi`。當 vendor onboarding 寫錯某 row NPI（譬如 Ashley row 的 NPI 寫成 Bassett 的 1790962041），SELECT 回兩 rows，loop 取 PK ASC first → 提交 order 時 customer_id 用了 Ashley (47549) 而非 Bassett (47715)。修法：MyBatis criteria 加 `.andCustomerProviderNpiEqualTo(npiNumber)`
- **避雷準則**：任何「gRPC / 上游回 list of IDs → SQL 用 IN(...) → 取 first」這類 pattern，**SQL 必須 redundantly verify 所有 lookup key**，不要假設 IN list 已經 100% 對。Defensive，不靠上游 cleanliness

### Reproducibility check 失敗 → 考慮 historical data state 不是當下 code bug
跑 standalone reproducer 模擬 prod path 但結果跟 prod log 不一致時，**先排除 historical data state 跟現在不同**這個可能性，不要直接斷定 code bug。特別當：
- 表沒 created_at / updated_at audit field（譬如 `order_clients`）
- 跨 system 數據可能由 vendor onboarding script / 人工 patch 修改（沒 application-layer trail）
- prod log timestamp 跟現在差距 > 幾天

EMR-Backend customer_id mismatch 案例：reproducer 用 current DB state 回 47715（正確），但 prod log 是 47549（錯）— 推論 4/27 處理時 `order_clients` 某 row 的 NPI 寫錯，後來修正了。沒 audit field 無法 100% 證明，但 fix 仍要做（防 future 同類）。

### Trace HL7 / token / log 對應時要 verify 是同一 trace
跨多個 source 看 prod issue 時（HL7 input + outbound API token + DB log），先 verify 它們**同個 order 的 trace**（用 file_name / sample_id / placerOrderNumber 對應），不要假設使用者貼的 sample 是同 trace 的不同 angle。EMR-Backend 案例：HL7 example + token JSON 看似同 order，但 reproducer 結果不對 — 後來確認可能 token 跟 HL7 不一定來自同 trace，或 4/27 DB state 不同。

### lis-backend-emr-v2 雙 MySQL Instance — ⚠ migration apply 已踩 3 次（VP-15460 / VP-16760 / INCIDENT-20260528）
- **Prod**: `lisportalprod2.mysql.database.azure.com:3306/lis_emr` (`.env` `DATABASE_URL`)
- **Dev / Staging**: `192.168.60.11:3306/lis_emr` (root password `s3cr3TL33tP@ssw0rd`，URL-encoded `s3cr3TL33tP%40ssw0rd`)
- **Schema migration 兩邊都要 apply** — release pipeline 不會自動處理（DB 沒 baseline 過 prisma migrations，跑 `prisma migrate deploy` 會 fail with P3005）
- **Apply 方式**: `DATABASE_URL="<dev-url>" npx prisma db execute --schema prisma/schema.prisma --file <migration.sql>` 然後再對 prod 跑一次（prod 用 `.env` 預設 DATABASE_URL）。或直接 `mysql -h <host> ... < migration.sql`
- EMR-Backend Java 也讀 dev DB（`generatorConfig.xml` 的 `192.168.60.11`）+ 同 prod DB → schema 改動兩個 repo + 兩個 DB 必須同步
- **驗證 SOP**：apply 後對兩個 DB 都跑 `SHOW TABLES LIKE 'new_table%'` 或 `DESC new_table`、寫進 ticket 結尾 checklist
- ⚠ `mysql ... | grep -v "Using a password"` 會吃掉 mysql 的 exit code（輸出全被過濾時 grep 回 1）→ DDL 成敗用 information_schema SELECT 驗證，別看 shell exit（VP-17344）
- **典型症狀**：FE call 該 table 的 endpoint 回 500、staging pod log 印 `prisma:error P2021 ... does not exist in the current database` (INCIDENT-20260528 reject endpoint 案例)
- **長期 fix**：把 migration apply 寫進 Jenkinsfile pre-deploy step（同時對兩個 DB 跑），不再靠人記得
- ⚠ **`.env` 的 `DATABASE_URL` 密碼是 URL-encoded**（含 `%xx`）：直接把那段字串餵給 `mysql` CLI 會 auth failed，要先 `urllib.parse.unquote`。踩過（HL7FAIL-20260730）：同一台機上唯讀帳號好好的，只有 app 帳號的 URL 需要 decode，很容易誤判成「密碼過期／權限問題」。
- **VPN 斷線時的替代讀取路徑（HL7FAIL-20260730 / 2026-07-31 dream 驗證）**：Azure prod MySQL 從本機要 VPN，但 **AKS prod pod 內直接連得到** —— `kubectl exec` 進 pod 用它自己的 `DATABASE_URL` + `@prisma/client` 跑 `$queryRawUnsafe` 就能查。`kubectl cp` 一支 node script 進 `/tmp` 最省事。**注意欄位名要先 `SHOW COLUMNS` 確認**：`hl7_file_input` 用 `received_time`/`updated_time`（不是 `created_at`），`result_transmission_records` 才是 `created_at`/`updated_at`；BusyBox 的 `grep` 也沒有 `--include`。

### redlock@4 API & CommonJS Interop
- **CommonJS-only package**: `module.exports = Redlock` (no `.default`, no bundled `.d.ts`)
- 這 repo `tsconfig.json` 只設 `allowSyntheticDefaultImports`、無 `esModuleInterop` → `import Redlock from 'redlock'` 編譯成 `redlock_1.default = undefined` → **NestFactory startup crash**
- **修法**: `const Redlock = require('redlock'); type Lock = any;`
- **redlock@4 vs @5 API 差異**（容易踩雷）:
  - `Lock.prototype` v4 只有 `unlock()` + `extend()` — 沒有 `release()`（v5 才有）
  - `Redlock.prototype` v4 兩者都有 (`release` 是 `unlock` 的 alias)
  - 寫 wrapper 時用 `lock.unlock()` 不是 `lock.release()`，否則每次釋放都 throw（cosmetic 但會被 TTL 蓋過）
- **避雷**: 任何新 npm dep 上 prod 前跑 `node -e "const X=require('x'); new X(...)"` 確認 instance 能建（光 `tsc --noEmit` 過不代表 runtime OK）

### Cron Handler + Redlock Auto-extend = Lock Leak（INCIDENT-20260528）
Pattern：cron handler 拿 redlock → 開 `setInterval` auto-extend lock TTL → `await runWork()` → `finally { release }`。若 `runWork()` 永遠不 resolve/reject (e.g. ssh2-sftp-client `client.list('.')` 在 server 偶發慢時的 promise leak)：
- `finally` 永遠不跑
- `setInterval` 仍持續 extend lock
- **lock 永遠不過期** → 後續每個 cron tick 看 lock held → skip → **整條 pipeline 無限 outage**

INCIDENT-20260528 因此卡 19h、零 fetch。同類 bug 之前在 BullMQ worker (INCIDENT-20260518 mode B) 出現過、教訓沒推廣到 cron handler → 又踩。

**強制規則** — 任何「lock + auto-extend + await work」的 code path 必須三層 timeout：
1. **Per-work-item timeout**（e.g. per-folder, per-job）— `Promise.race(work, setTimeout(reject))`、單一壞 item 不卡整 run
2. **Whole-run hard timeout**（< cron interval / lock TTL ceiling）— 防 work-item timeout 本身失靈
3. **Force-release timer (defence in depth)** — `setTimeout(() => release(), MAX_MS)`、配 `releaseOnce` dedupe guard、保證 lock 一定在 hard deadline 釋放

實作參考：`Hl7OrderFetchService.handleCron` PR #135 (`bugfix/leo/v2-fetch-hang-timeout`)、`Hl7OrderFetchService.runWithTimeout(op, ms, label)` helper、env override `HL7_FETCH_MAX_RUN_MS` / `HL7_FETCH_FOLDER_TIMEOUT_MS`。

對應 BullMQ 版見 INCIDENT-20260518 / `result-generation.processor.ts` 的 `Promise.race` outer wrap。

### Singleton + unbounded `await network.close()` = service-wide deadlock（INCIDENT-20260601 教訓）
`SftpConnectionService` 是 NestJS singleton，`this.client` 一份共用。`safeDisconnect()` 寫 `await this.client.end()` **無 timeout** + `finally { this.client = null }`。當 vendor SSH 半關閉（TCP/banner 都通但 channel 關掉、never 回 SSH_MSG_DISCONNECT ack）時：
- `await client.end()` 永遠不 resolve → `finally` 永不執行 → `this.client` 仍持有 stale handle
- 後續任何 caller（cron tick / BullMQ worker / gRPC handler）走 `connect()` 第一步 `safeDisconnect()` 也卡在同一個 await → 整個 service 跨多 caller deadlock
- k8s readinessProbe 不檢 SFTP，pod alive、CPU 低、log 完全靜默 6~13 分鐘自癒（OS TCP keepalive ~2h + BullMQ JOB_HARD_TIMEOUT 600s 才釋放 worker slot，但 socket op 本身仍 leak）

**強制 pattern** — 任何 singleton 內 `await externalConn.close()` / `await client.end()` / `await session.disconnect()` 必須：
1. **先清 shared mutable state**（`this.client = null; this.isConnected = false`），再 await — `finally` 不保證會跑
2. **`Promise.race` + 5s timeout** — peer 不 ack 也要在固定時間後放手
3. **保證 peer-visible teardown 的 3-stage close**（INCIDENT-20260604 修正：原本的 `_sock?.destroy?.()` fallback **不夠**，詳見下節）

實作範本：`SftpConnectionService.forciblyClose()` 於 `bugfix/leo/INCIDENT-20260604-mdhq-leak` merge 後成為 canonical 範例。詳見 [[INCIDENT-20260601-sftp-hang]] [[INCIDENT-20260604-mdhq-stale-connections]]。

### 3-stage clean close — 為什麼 `socket.destroy()` 單獨不夠（INCIDENT-20260604）

**踩雷**：INCIDENT-20260601 patch 用 `(c).client?.end?.(); (c).client?._sock?.destroy?.();` 當 timeout fallback，pod 端解了 hang，但 MDHQ Bitvise WinSSHD 仍報每天 20 個 stale session。原因：
- `ssh2.Client.end()` 是 async，呼叫後 SSH_MSG_DISCONNECT bytes 還在 ssh2 internal write queue 沒寫進 socket
- 立刻 `_sock.destroy()` → kernel `close(fd)`，queue 內 bytes 丟掉
- `socket.destroy()` 不保證送 TCP FIN（buffer 狀態決定送 FIN 或 RST 或啥都沒送，per SO_LINGER 與 send buffer）
- SSH daemon（如 Bitvise）在 application layer tracking session — 沒收到 SSH_MSG_DISCONNECT 就把 session 留在 "abandoned" 狀態幾小時等 idle reaper

**正確的 3-stage 順序**：

```typescript
private async forciblyClose(c: any, label: string) {
  // Stage 1: ssh2-sftp-client.end() bounded — sends SSH_MSG_DISCONNECT + FIN
  try {
    await Promise.race([c.end(), timeout(5000)]);
    return; // clean
  } catch (err) {
    if (isECONNRESET(err)) return; // peer 已先關，also clean
  }
  // Stage 2: socket.end() — explicit TCP FIN，等 'close' event 或 500ms drain
  const sock = c?.client?._sock;
  if (sock && !sock.destroyed) {
    await new Promise(resolve => {
      const timer = setTimeout(resolve, 500);
      sock.once('close', () => { clearTimeout(timer); resolve(); });
      try { sock.end(); } catch { resolve(); }
    });
  }
  // Stage 3: socket.resetAndDestroy() — 保證送 TCP RST (Node 18.3+)
  if (sock && !sock.destroyed) {
    if (typeof sock.resetAndDestroy === 'function') sock.resetAndDestroy();
    else sock.destroy();
  }
}
```

每個 stage 對應一種 peer 行為：
| Peer 行為 | 觸發 stage | Peer 收到 | session 清乾淨？ |
|---|---|---|---|
| Normal | Stage 1 resolve | SSH_MSG_DISCONNECT + FIN | ✓ |
| Peer 先關 | Stage 1 ECONNRESET | (already cleaned) | ✓ |
| SSH 卡但 TCP 通 | Stage 1 timeout → Stage 2 | TCP FIN，peer 收到後 'close' event | ✓ |
| SSH + TCP 都不回 | Stage 1+2 timeout → Stage 3 | TCP RST | ✓（RST 是不可否認的訊號） |

實證：INCIDENT-20260604 patch deploy 後 2h 觀測，**1939 graceful + 10 econnreset + 1 fin_then_rst = 0 leak-equivalent outcome**。

### 衍生規則 — abandon-client 路徑全部走同一個 helper

INCIDENT-20260601 patch 另一個 gap：`connect()` retry loop 失敗時 cleanup path 不同（沒嘗試呼叫 `client.end()`，直接 destroy），每次 vendor throttle = retry × destroy = peer 端累積 abandoned session。

**規則**：每個 abandon-client 路徑（`safeDisconnect` / `connect` retry / 任何 catch + cleanup）都必須走同一個 `forciblyClose(client, label)` helper。Cleanup code 在多處複製 = 一處改、其他處 leak 仍在。

### 衍生規則 — NestJS app 必啟用 enableShutdownHooks()

`main.ts` 沒 `app.enableShutdownHooks()` → `OnApplicationShutdown` / `OnModuleDestroy` 在 SIGTERM 時不會跑。pod restart（每次 deploy 必發生）= 所有 in-flight network handles 直接被 process exit 殺，peer 看到無預警 RST 或卡住 session。

任何包 network handle 的 NestJS provider 必須：
1. `implements OnApplicationShutdown` (and/or `OnModuleDestroy`) 並在裡面 await 清乾淨
2. `main.ts` `app.enableShutdownHooks()` 啟用

### 衍生規則 — 修 network lifecycle bug 必驗 peer-side observable state

INCIDENT-20260601 retro 的 success criterion 只有「pod 不 hang」，沒驗 peer 看到什麼 → 留下 leak 沒抓到（INCIDENT-20260604 浮現）。

修 network handle lifecycle 的 PR，verify plan 必須包含：
1. 我方 side（pod metric / log）— 你的程式邏輯確實過了
2. **peer side（vendor session count / netstat / 從 their reports）** — 對方真的看到 teardown

如果 peer-side observability 不可得，至少從 pod 內 `netstat -ntp` 看 connections to peer over time，確認 ESTABLISHED 不會累積。Per [[verified-means-live-not-mock]]：自己 log 顯示 "disconnect succeeded" ≠ peer 真的看到 disconnect。

### 衍生規則 — 高頻 lifecycle event 監控用 structured grep-anchored log

INCIDENT-20260604 deploy 前加了 single-line `[SFTP_CLOSE] label=... outcome=... totalMs=... [escalated=...]` 每個 disconnect 一行，outcome 列舉所有可能值。Deploy 後 2h 用 `grep -oE 'outcome=[a-z_]+' | sort | uniq -c` 立刻看哪一條 path 多。

Pre-INCIDENT-20260604 的 log 是 `Disconnecting from SFTP server` 後可能跟 `force-destroying socket` warning — 沒結構、要 sample manually、6min 內 200+ 行很難看。

**規則**：高頻 lifecycle event 監控想 deploy 前 build-in structured log。pin format 一個 unit test 防後續 refactor 破壞 grep。outcome 列舉「健康」vs「不健康」outcomes，前者 log 後者 warn — 自然形成 alert stream。

**衍生規則 — singleton network handle 的設計選擇**：包 network connection 的 NestJS provider 預設不要用 `@Injectable()` default singleton scope。考慮：
- `Scope.TRANSIENT` per-caller instance — handshake 成本換 isolation
- 手刻 connection pool keyed by `host:port` + acquire/release semantics
- 至少：每個 method 帶 per-op timeout（不只 connect/disconnect，list/put/get/stat 全部）

**狀態更新（2026-06-25 查證）— POD_ROLE 分流 fix 寫好了但「從未部署」到 on-prem prod**：症狀重現——「result 在跑時 order(-fetch) cron 一觸發就卡住」。根因鏈：`SftpConnectionService` singleton 共用 `this.client`、`connect()` 第一行無條件 `safeDisconnect()`（`sftp-connection.service.ts:47-48`）+ 無 mutex；`Hl7OrderFetchService` `@Cron('0 */15 * * * *')` 每 15min 逐 folder `connect()`（line 269）→ 把正在 `put()` 的 result 上傳那條 socket 砍掉 → 上傳等不到 ACK 卡到 10min timeout / 噴 `Unexpected end event`（單日 6000+ 次）。`config/pod-role.ts` 的 intake/pusher 分流就是為此而寫，但**兩個 on-prem pod（`lis-emr-v2-deployment` app=lis-emr-v2、`lis-emr-v2-deployment-prod` app=lis-emr-v2-prod）spec 都沒設 `POD_ROLE` → 全 fallback `all` → 分流從沒生效**。**且不能直接設 env 分流**：兩 pod 都 `REDIS_HOST=localhost`（各自 redis sidecar，不共用），而分流設計靠**共用 Redis** 當 intake→pusher 的 result-gen job 橋樑（kafka 自動路徑）→ 直接分流會斷掉自動 result 路徑。**故 connection pool（上方 line 456）才是較可行的正解**，而非 POD_ROLE 分流（後者還要先補共用 Redis + 第二個 prod deployment + result-gen gRPC Service `lis-emr-v2-internal-prod`/`-nodeport-prod` :5000 確認指向 pusher）。prod result-gen 走同步 gRPC `GenerateBatchResultsHl7`（inline 不經 queue，`isPusher` gate）；自動結果才走 kafka→queue。

**衍生規則 — 操作症狀重複出現要 escalate 到 code 層**：INCIDENT-20260528（5/28 同症狀 SFTP fetch hang）只記「rollout restart 解決」，沒追到 singleton 層 root cause；6/1 同樣 hang 再現、阻塞 157-sample batch retry。**第二次出現相同症狀的 incident，retrospective 必須有 code-level analysis section**，不只記 mitigation。

### lis-backend-emr-v2 SFTP fetch loop 對同一 host 重複 connect overhead
`SftpConnectionService` 是 singleton、shared `this.client`。`Hl7OrderFetchService.processFolder` 每個 folder 都 `safeDisconnect → connect → listFiles → ... → disconnect`。MDHQ 一台 host (`34.199.194.51:2210`) 上有 172 個 sub-folder mapping → **單一 cron tick 對同一 host 做 172 次 connect/disconnect**。

副作用：
- `connect()` 內含 `client.list('.')` 作 session validation，MDHQ home dir 有 172+ subdir → 每次 list 不便宜
- ~7min 內 172 次 connect/listdir → MDHQ server 偶發回應慢、那次 `list('.')` 卡 > per-folder timeout → log 印 `Folder id=X emr=MDHQ exceeded 120000ms — moving on`（X 是 transient、不是固定 hang folder）
- INCIDENT-20260528 21:45 tick 抓到 id=260、22:00 tick 同 folder 順利 → 證實 transient

**長期 fix（follow-up ticket）**：folder by-host grouping、單一 host 共用 SFTP connection 跑完所有 folder 再 disconnect。172 次 connect → 1 次。也避開 server rate-limit-ish 行為。

### SFTP host reachability test 必查 `emr_sftp_source.port`
踩雷：`nc -z host 22` 對非標準 port 的 vendor 等於沒測 → 誤判 dead host (INCIDENT-20260528、VP-16180 同類)。
- PF: `45.24.217.150:2222`
- Breathermae: `64.124.9.100:2222`
- MDHQ: `34.199.194.51:2210`

任何 host reachability check 都先查 `ehr_vendors` 的 host/port 欄位取真實 port（`emr_sftp_source` 已於 2026-07-20 退役，VP-17460 — credential/host 單一來源見 emr-integration.md）。

### SFTP 連不上的兩種模式要先分清楚（INCIDENT-20260529）
**(a) Server down / 網路不通**：`nc -zv host port` 直接 TCP fail。

**(b) Auth rejected — TCP 通 + SSH handshake server close（vendor 端問題、不是 code）**：
- `nc -zv host port` 成功
- ssh2-sftp-client 印 `getConnection: Unexpected end event`
- 直接 `ssh -p N -o PreferredAuthentications=password user@host` 印 `Permission denied (publickey,password)`
- paramiko 印 `Authentication failed: transport shut down or saw EOF`

(b) 的常見原因：vendor 改 IP 白名單、rotate 密碼、帳號因失敗次數鎖。**code 完全正常、別動 code、別 rollback**、PM 聯絡 vendor。

INCIDENT-20260529：MDHQ host `34.199.194.51:2210` 5/29 11:16 UTC 起進 (b) 模式、20h 內每 15min cron tick 撞 force-release timeout（PR #135 timeout fix 因此被 prod 實戰驗證）、非 MDHQ 24 個 vendor 全正常。診斷順序：(1) `nc -zv` 區分 (a)/(b) → (2) 看 ssh2-sftp-client / paramiko error 字串 → (3) 確認其他 vendor 通不通 → (4) PM 聯絡 vendor。

### UPDATE-WHERE-JOIN scope 必反向 audit（NULL semantics 陷阱）
SQL 標準 `NULL = NULL` 是 false。`UPDATE ei JOIN oc ON oc.X = ei.X WHERE ...` 在 X 兩邊都 NULL 時 silently 漏掉那 row、ROW_COUNT 看起來正常但實際 scope 不完整。

INCIDENT-20260529 案例：customer 508387 Sano Health Club，oc.clinic_id=508387 / ei.clinic_id=19232（不同）、customer_provider_NPI 跟 customer_npi 兩邊都 NULL → `(oc.cust=ei.cust AND oc.clinic=ei.clinic) OR (oc.NPI=ei.NPI)` 兩條 branch 都 false、JOIN miss 整 row。Leo 直接點名 508387 才被抓出來。

**SOP**：對 prod 跑 batch UPDATE-WHERE-JOIN 後、用更廣的 criterion 反向 SELECT 找「應該在 scope 但 JOIN 漏掉」的 row。例：原本用 `(cust+clinic) OR NPI`、反向用 `customer_id alone + EXISTS oc match + 同樣 WHERE flag` → 抓 NULL/clinic_id-mismatch 漏網。NULL-safe 操作符可用 `<=>` 或 `COALESCE`/`IS NULL` 顯式處理。本檔 280 行的「pre-UPDATE SELECT 比對 + transaction rollback」是不同階段的另一道防線（不衝突）。

### MyBatis Generator + Hand-added Statements
- EMR-Backend `generatorConfig.xml` 列出的 table（`sftp_folder_mapping` 等）會被 MyBatis Generator 重新生成 entity / mapper interface / XML
- 想加自訂 SQL 又不想被 regenerate 蓋掉 → 在 mapper XML 加新 `<select id="...">` 並用 hand-comment 標 「VP-XXXX hand-added, not generator-managed」
- Java 側用 `MybatisSession.sqlSessionFactory.openSession()` 直接呼叫 statement string（如 `com.vibrant.emr.mapper.FooMapper.selectXxx`），繞過 `DatabaseService.execute` enum-based API
- 不要動既有的 `selectByExample` 加 WHERE — 會影響全 codebase 的 caller

### Confluence 大頁面用 fetch + ARI 形式
讀大型 Confluence PRD（如「Automated New EHR Integrations」）時，`getConfluencePage` 回 ADF JSON 容易超 token 限制，改用 `mcp__claude_ai_Atlassian__fetch` 取 markdown 形式。**ID 必須是 ARI 格式**：`ari:cloud:confluence:<cloudId>:page/<pageId>`，純 page ID 會 fail。VP-16165 驗證。

### Bash Tool cwd Persistence (Cross-Repo Flows)
- Bash 工具的 `cd` **跨 call 持續**，下個 Bash call 沒指定就用上次的 cwd
- 跨 repo 的 commit/branch/PR 流程要每次 explicit `cd <abs-path>` 開頭，不然會在錯 repo 開 branch（已踩過）
- 確認當前位置: `pwd && git branch --show-current`

### Ticket 已有 MERGED PR ≠ 核心需求做完
看到 ticket 連結了 MERGED PR 不要假設工作已完成。`git log` 看 commit 實際動的檔案，比 ticket comment / PR 標題可靠。VP-16361 案例：linked PR 已 merged 但只動了 schedule/availability，沒動 auth 邏輯（核心需求）。

### PRD「To X」字面化 vs deployed 行為衝突時先 raise（VP-16502 教訓）
PRD 寫「Reminder (To Provider)」這類用語不要直接讀為「only Provider」加 filter。**deployed prod 行為 + 既有 explicit test assertion 是 design intent 的硬證據**，比 PRD wording 更權威。判斷流程：
1. 草 AC 階段就 flag「PRD wording 對 X 是 only-X 還是 at-minimum-X」當 Open Question
2. 跟 deployed test 衝突時不要改 test 配合 AC，先 raise 給 PRD owner / Leo 確認
3. VP-16502 case：原 AC4「filter clinicadmin from reminder」加 filter 後 8 個 VP-16391 test fail；revert 並 raise，Leo 確認 PRD #3「To Provider」是 at-minimum，AC4 改寫成「保留既有 all-participants 行為」no code change

### Cross-cutting helper 抽不乾淨時 in-place 比 over-DRY 好（VP-16502 教訓）
5 個類似 send method 各加 cross-recipient loop 時，原想抽 helper 集中。但每個 method 的 templateModel fields 不同（PRD 7 scenario × 2 recipient role 不互通），抽 helper 要 switch by `(notificationType, recipientType)` 變得醜。**直接 in-place duplicate**（每 method 加 ~30-50 行）比 over-DRY helper 讀起來更直白。判別：cross-cutting code 的 variant 維度 > 2（這個 case 是 7 × 2 = 14 種 templateModel）→ 用 helper 反而 ugly switch；維度 ≤ 2 → 抽 helper 划算。

### Leo 自然語言指示要先列解讀分歧
Leo 用自然語言下指示（例 "participant 裡面有 patient"）可能有多種解讀（純結構檢查 vs 含 caller 驗證）。**先呈報解讀分歧、各自符合哪些 AC，由 Leo 確認後再實作**，不要假設後返工。VP-16361 案例：先列出兩種解讀後 Leo 選方案 B，省了重做。

### STM 引用 — Decisions 區段不是 final source of truth
STM 的 `## Decisions Made` 區段是「Step 5 執行前的當下決策草稿」，Step 6 review 時 Leo 推翻或調整的部分**未必會回填**。引用過去 STM 的決策做新 ticket 預設前：
- 優先讀 `## Code Changes` / `## Test Results` / `## Failures` 三段（這些是 final state 的紀錄）
- 對牽涉 prod DB 值的決策，直接 `SELECT` 實際 row 確認，不靠 STM 文字
- VP-16424 教訓：引 VP-16423 STM line 173 「kit_delivery_option=BOTH_BLOOD_AND_NON_BLOOD」當 follow 範例，但 DB 實際是 NO_DELIVERY（Leo 即時指正）。LTM `emr-integration.md` line 436 已寫對 → 多比對 STM vs LTM 不一致時優先 LTM

### Merged PR 不能在原 branch 修
要 push 修 fix 到既有 PR branch 前先 `gh pr view <num> --json state,headRefOid`，確認 state=`OPEN`。若已 `MERGED`：
- GitHub 通常 merge 後刪除 source branch，但本地 stale ref 仍在 → `git checkout feature/leo/<id>` 會成功（從 stale ref 建 local branch），push 會 `* [new branch]` 重建一個沒 PR 包它的孤兒 branch
- 正確做法：從 `origin/stage_test`（或對應 base）開新 branch（譬如 `bugfix/leo/<id>-<topic>`）→ cherry-pick 修補 commit → push → 開新 PR
- 若意外重建了原 branch：commit cherry-pick 到正確 branch + 新 PR 後，用 `git push origin --delete <merged-branch>` 移除孤兒 remote branch（destructive，要 Leo 同意）

### Postmark template Mustachio i18n section
PM 把 staging template body 包在 `{{# English}}...{{/ English}}`（Mustachio conditional section）但 prod template 是 flat。caller 端要根據環境切 TemplateModel 結構：staging 傳 `{ English: { time, ... } }`，prod 傳 flat。**`{{# X}}` section 在 X falsy 時會 skip 整個區塊**，沒帶語言 flag → 整封 email body + subject 都空。

判斷 staging：`EmailTemplateConfigService.isStagingEnvironment()`（`NODE_ENV='test' || SERVER_ENVIRONMENT='stprod'`）。同樣的判斷已在 `getTemplateId()` 用過，新 caller 用此 helper 而非重複條件。

### Postmark template debug 流程
Email body 空時依序檢查：
1. **template HTML body 是否被 i18n section 包**（語言 flag 沒帶 → 全空）
2. 變數命名大小寫（Mustachio 大小寫敏感，`{{Time}}` ≠ `{{time}}`）
3. `defaultFields` (yaml) 是否被 templateModel override（line 192-196 priority: defaultFields ← dynamicColors ← templateModel）
4. `v2_reminder_audit_log.status='sent'` + Postmark dashboard activity 都正常 → 多半是 (1)/(2)

### DB-only ticket 不建 git branch
EMR integration ticket 若只動 DB（無 code change）不建 git branch、不 commit。「永遠先建 branch」規則的精神是改 code 前；純 DB 操作建 branch 只是空 branch。例外：要產 SQL/script 進 repo 時才建。VP-16175/VP-16193/VP-16245/VP-16251/VP-16329 連續驗證此 pattern。

### lis-backend-emr-v2 HL7 Decoder MSH segment 解析索引
`Hl7DecoderService.parseSegments` 對每個 segment `split('|')` 後 `slice(1)`（去掉 segmentType）。對 MSH segment：`fields[0]` = MSH.2 (encoding chars `^~\&`)，`fields[N]` = MSH.(N+2)。常用映射：
| 想要的欄位 | fields 索引 |
|---|---|
| MSH.2 (encoding) | fields[0] |
| MSH.3 (sending app) | fields[1] |
| **MSH.4 (sending facility)** | **fields[2]** |
| MSH.5 (receiving app) | fields[3] |
| MSH.6 (receiving facility) | fields[4] |
| MSH.7 (timestamp) | fields[5] |
| MSH.9 (message type) | fields[7] |

**Defensive 必加**：抽 MSH 任一欄位前先驗 `fields[0]?.includes('^')`（encoding chars 的 marker）；異常就 warn + return null，避免錯把鄰近欄位當目標欄位。對非 MSH segment（ORC/OBR/PID 等）`fields[N]` = `<segmentType>.(N+1)`，索引規則不同。

### lis-backend-emr-v2 Clinic-Level Catch-all Marker
`ehr_integrations.customer_id = '-1'`（**string**，因 customer_id 是 `VarChar(255)`）標記「clinic-level catch-all integration」，不對應特定 provider，掛在 `clinic_id` 上做 practice-wide 路由。將來 `practice_integrations` 表獨立後此慣例會搬遷（PRD：EHR Integration Enhancements V2 / VP-16164）。新加 clinic-level integration 時必須寫 `customer_id='-1'` 才會被 fallback lookup 命中。VP-16165 驗證。

### lis-backend-emr-v2 ehr_integrations.clinic_id 是 Int?
比對前必須 `Number(raw)` 並驗 `Number.isInteger`（`schema.prisma` 標 `clinic_id Int?`）。對 string 比 string 會 prisma type error。`customer_id` 反而是 `String VarChar(255)`，所以 `customer_id = '-1'` 是 string literal。

---

## Default Practice Event Type — Resolution Pattern (LIS-transformer-v2)

`getDefaultPracticeEventType(practiceId)` 在兩處重複實作：
- `src/calendar/models/event/event.service.ts:2950`
- `src/calendar/models/meeting-request/meeting-request.service.ts:905`

兩份邏輯一致：先查 `name='General'`（per practice exact match），找不到 fallback 到「最小 ID active type」（findFirst with `orderBy.id asc`）。`v2_practice_event_type` 唯一鍵 `[practice_id, name]`。Default seed 在 `src/calendar/models/shared/practice-event-type-defaults.ts`（Follow-up / Checkup / Initial Consultant / General）。

### VP-16416 — Clinical Consult per-practice override
practice_id=150105 用 special-case：先查 `name='Clinical Consult'`，**不可用就 `logger.logWarn` 後 fall through 到原有 General → first-active 邏輯**（PM 偏好 graceful fallback over strict throw，warn log 提供 audit 即可滿足「no silent fallback」）。其他 practice 維持既有邏輯。

### Future option (deferred)：DB-driven per-practice default
通用化方向：給 `v2_practice_event_type` 加 `is_default` BOOLEAN 欄位，每 practice 一筆 `is_default=true` 的記錄；resolution 邏輯改先查 `is_default=true` 再 fallback。優點是 admin UI 可切換 default、不再 hardcode practice ID。缺點是需 prisma migration + seed + 跨兩份 service 同步改、影響面大。Leo 2026-05-04 決定先做 special-case (A)，B 留做後續若多 practice 需要 customize 時再做。同步要把 meeting-request.service.ts 的重複實作也改掉以保一致。

---

## Clinical Consult Calendar (practice_id=150105) Email Flow

LIS-transformer-v2 的 calendar email pipeline 結構（VP-16413 / VP-16391 釐清）：

### createEvent vs createEventByPatient — 收件者（VP-16502 後雙方都收）
| 面向 | `createEvent` (staff books) | `createEventByPatient` (provider as seeker) |
|------|----------------------------|---------------------------------------------|
| Primary loop | patient role | provider/clinicadmin role |
| Cross-recipient loop (clinician event only) | provider/clinicadmin role | patient role |
| Send 函式 | `sendAppointmentScheduledEmailForCreateEvent()` | `sendAppointmentScheduledEmailToNonPatients()` |
| Postmark templates (prod, clinic_id=150105) | `33802988` (patient) + `34153520` (provider, VP-16502 cross) | `34153520` (provider) + `33802988` (patient, VP-16502 cross) |
| practice_id 限制 | 任意 | 寫死 `150105` (CLINICIAN_PRACTICE_ID) |

**VP-16502 (2026-05-07) 之前**收件者非對稱（actor doesn't get notified pattern）：createEvent 只發 patient、createEventByPatient 只發 provider/clinicadmin。PRD 要求兩邊都通知，所以 6 個 send method (`sendAppointmentScheduledEmailForCreateEvent` / `...ToNonPatients` / `sendAppointmentCanceledEmails` / `...EmailToNonPatients` / `sendAppointmentUpdatedEmailToPatient` / `...EmailToNonPatients`) 各加一個 cross-recipient loop，gated by `isClinicianEvent(event)` 保護非 clinician practice 行為不變。`email-templates-clinician.yaml` 加 6 個 cross-recipient entries 都 map 到既有 Postmark id（不開新 template）。reminder 維持 VP-16391 既有「all participants 都發」設計，不過濾 clinicadmin。

兩 flow 都 publish 同一個 Kafka `Appointment Created` event 到 `general-sample-events`，但 email 是 transformer-v2 直接 publish 到 `notification-email-template` topic（不走 setting-consumer Bull queue）。

### Postmark template 設定位置
`LIS-transformer-v2/src/calendar/models/notification/email-templates-clinician.yaml` — YAML 列出 clinic_id=150105 所有 template ID（prod/staging），改 ID 改這個檔。

### Kafka 雙 broker 佈局
| 用途 | Broker (env var) | Topic (default) |
|------|------------------|-----------------|
| Appointment events | `Azure_kafka_general_events` | `general-sample-events`(prod) / `general-sample-events-staging`(staging) |
| Email payloads | `Azure_kafka_notification_url` | `notification-email-template` |

兩 broker 都 SASL plain + ssl + `$ConnectionString` 帳號。注意 broker 跟 appointment 不同 namespace。

### Silent-failure bug class（跨 ticket 蒸餾 2026-07-06；更新 2026-07-22；9+ 案例）
同一族 bug 在不同 repo/模組反覆出現 — 失敗被吞掉或被 coerce 成合法值，數週到數月無人發現。review / debug 時先掃這幾種 shape：
1. **`.catch((error) => logger.error(...))` 吞 exception**（VP-16413, transformer-v2 `event.service.ts:1574`）：email 失敗 silent，前端成功、無 audit trail。
2. **per-item catch 只印 `error.message`，而 message 是空的**（VP-16987, emr-v2 quarterly report）：Prisma error message 為空 → createMany 失敗隱形數月。排查時先把 catch 改印 stack / 觸發真實路徑。
3. **invalid response coerce 成預設值**（VP-17318）：`parseInt(response.sample_id || '0')` + 讀錯 proto 欄位名（`sampleId` vs `sample_id`, keepCase）→ RPC 自 VP-16463 port 起從未 work，下游 sendOrder 收 0 會自行分配 id，進一步掩蓋。
4. **event consumer 查無 match → return + commit offset，只留 debug log**（journal 2026-07-02, kafka-report-finished-listener:268）：result 永久丟失、`result_transmission_records` 0 rows、prod 看不到 debug log。
5. **processor 假設 service 會 throw，但 service 用 return code 回報失敗**（VP-17342, emr-v2 result-generation）：`generateResultHl7` catch-all 後 return `{success:false}`，processor 從不檢查（註解還寫錯說 service 會 throw）→ BullMQ 標 completed：無 retry、無 ERROR record、無 alert；transmission record 建立前的失敗連 DB 痕跡都沒有。Fix = processor `if(!result.success) throw` + service 補 `[RESULT_SILENT_DROP_GUARD]` 結構化 log。通則：跨層的錯誤傳遞約定（throw vs return code）要在呼叫端讀 callee 實作驗證，不能信註解。
6. **success 判定用「沒有 error」而不是「有 success artifact」**（兩例，2026-07-13/14）：(a) VP-17286 Defect A — finalizer 為 legacy 語意 catch placeOrder 錯誤後 return `{sampleId:null}`，intake 端把 null 當 placed → API 回 `201 placed` 但 order 不存在（與 #5 同 class：legacy-tolerant catch 被 reuse 到「caller 把 null 當成功」的新路徑）。(b) VP-17411 PR #264 — charging 對 stripe 回 2xx `requires_confirmation` 且 payment_id 空，finalizer success check 只看 `!errorMessage` → HL7 order 出貨未收費且**連 fail reason 都沒記**（比修 #255 前更不可見）。Fix 通則：**success = 必須拿到 success artifact（payment_transaction_id / sample_id），不是沒看到錯誤**。
7. **雙 store fallback 讀取，缺 row 只留 debug-level warn → folder 靜默跳過**（VP-17385, FOLLOWTHATPATIENT order 卡 2 天）：兩份憑證表「靠習慣同步」必然 drift，且失敗模式是靜默 skip。Consolidation > sync 紀律；過渡期 drift 要 WARN（只印欄位名不印值）。
8. **fail-open 分散式鎖：lock 取得失敗 `catch → return true`**（VP-17422, transv2 daily report）：redis 錯誤被 coerce 成「我拿到鎖」→ N replicas 全部執行 → 每個 weekday 3 份重複 email，結構性（非 intermittent），因為錯誤是 **NOPERM（permanent class）**——retry 也救不了，我第一版 retry+fail-closed fix（PR #536）因此無效且會變成「永遠不寄」silent outage。教訓兩層：(a) at-most-once 語意的鎖絕不能 fail-open；(b) 修 lock 前先分類錯誤是 transient 還是 permanent（permanent → 根治權限/改承載層，不是 retry）。**當 redis 不可信時，once-per-day claim 用 DB unique-INSERT**（`daily_report_run(report_date PK)`，第一個 INSERT 贏、P2002 = skip、DB error = fail-closed）——calendar DB 本來就是該 cron 的依賴，可靠性綁定正確。2026-07-17 prod 實證：1 row / 1 claimant / 1 send。
9. **failure record 寫進沒人讀的表**（VP-17474, 2026-07-22, 20h prod email outage）：deploy 後 schema 缺欄位 → token issuance Prisma create 全數失敗，失敗被 catch 寫進 `failed_notification`（`retried` 欄位寫 false 但零 code 讀它）→ 265 封 result-ready email 靜默未寄、無 alert 無 retry，20 小時後靠人工 ground-truth check 才發現。寫 failure record 時要問「誰讀這張表？」— 沒有 reader（cron/alert/dashboard）的 failure log 等於沒記。同 ticket 附帶發現 **Postmark suppression list 靜默擋信**：7 個 clinic inbox（HardBounce/ManualSuppression）從收不到任何 result-ready email，該 server 共 16,828 個 suppressed addresses — 「已發送」≠「已送達」，email 類 triage 必查 suppression dump（見 emr-integration.md deep-link 節）。
Rule：失敗要 loud（warn+ level、留 DB 痕跡、reject invalid input）；預設值只留給合法缺省語意。已提案 agent-core universal lessons（PR #2 fail-loud、golive-backfill PR）。
衍生紀律（VP-17286/17411, journal 2026-07-14）：
- **改 shared code path 後，逐一走每個 caller 的「失敗可見性」語意**（不只 happy path）：#255 改共用 charge block，API path 正確被擋，HL7 path 卻從「400+fail reason」變成「2xx 無痕出貨」。Leo 一句「修改的部分只有API嗎?」逼出 re-derivation 才發現 — 人類問「這改動只影響 X 嗎」時，答案要重推導不能憑印象。
- **Mock-seam 盲區**：兩個 Defect 都活在 unit test mock 掉的元件接縫（spec 的 synthetic fixture 設了 live pipeline 從不設的欄位，如 `of.customerId` — repo-wide grep 零賦值）。新 API path 上線前必須至少一輪 live E2E；寫 spec 時 fixture 欄位要對照真實 assemble 路徑，不要自己補全。

### 共享表加 scope/partition 欄位 → 全表讀寫點逐一 audit（跨 ticket 蒸餾 2026-07-09；VP-17312/17343/17344）
同一晚兩張 ticket 都被 Cursor bot 抓到「加了 scope 欄位但漏掉某個 call site」的 HIGH：
- VP-17312 PR #239：`findDistinctEligibleResultIntegrations` 無 `pipeline_location` filter、TIMEOUT_RETRY enqueue 不帶 integration_id → on-demand/repush 路徑 location-blind（→ 開 VP-17343 補 per-integration fan-out + ownership WARN）。
- VP-17344 兩輪：listener 自己的 `ensureTransmissionRecord findFirst` 漏 `push_scope_key: null`（新 partial record 會被 whole-order 路徑重用）；processor 的 retry/failure `updateMany` 用 scope filter 會誤寫舊 TRANSMITTED sibling → 改帶精確 `transmission_record_id`。
**SOP**：加 scope 欄位後，grep 該表**所有** `findFirst/findMany/updateMany/create` call site，逐點決定「帶新欄位 / 顯式 `null` / 精確 record id」——「這張 ticket 沒動到的 call site」正是最會漏的；舊資料（欄位=NULL）與新資料的互不干擾要靠顯式 NULL scope，不是靠沒寫。

### Status 欄位不是 ground truth — 據以行動前先驗 deploy 鏈（跨 ticket 蒸餾 2026-07-22；一週內 4 案例）
Jira/local status 與 prod 真實狀態一週內四度背離，方向各異：
- VP-17474：Jira 手動 Done、resolution 寫「clinic-level validation has been changed」當下，prod DDL 未跑、20h email outage 進行中。
- VP-17466：merge + deploy + live-verified 後，Jira 仍是 Dev Blocked。
- VP-16832 / VP-17117：local completed，Jira 被 QA 踢回 QA Review。
- VP-17475：local done（code + staging E2E 完成），Jira Dev To Do（等 pricing prod deploy）。
紀律：任何「done / blocked / fixed」宣稱（Jira、他人 comment、自己的 STM）在據以行動或對外回報前，用 L4 驗證 closure chain（merge → deploy → DDL/manual steps → live probe）。status 欄位是「有人宣稱過什麼」的紀錄，不是系統狀態。
另一條同批蒸餾：**監控腳本不可 hardcode 目標的 snapshot identity**（pod hash / instance id）——VP-17312 check_stageb.sh 寫死 cloud pod hash，redeploy 後對著死 pod 驗「0 rows」全綠（false-clean）。目標 identity 每次動態解析（kubectl 查當前 hash），解析不到就 fail loud。
1. **JS `Date.toLocaleTimeString('en-US', {hour12: true, ...})` 不帶 `timeZone`** → 用 Node process runtime tz。Azure container 預設跑 UTC，導致 `21:00 UTC` 直接 render 成 `09:00 PM`，沒做時區轉換。VP-16202 (2026-04-17) 之前所有 calendar email send method 都踩這個。修法：用 `toZonedTime(date, tz)` 後再 `format(zoned, 'hh:mm a')`（`date-fns-tz`）。
2. **`resolveEventTimezone()` UTC fallback 不對稱**（VP-16202 引入時的潛在 bug）：`if (providerTimezone) return providerTimezone;` 沒擋 `'UTC'`，但下一行 `event.timezone !== 'UTC'` 有擋。命中第一個 provider/clinicadmin participant 的 calendar tz 是字串 `'UTC'` 就直接 render 成 UTC。兩個分支都要加 `!== 'UTC'` 才對稱。
3. **prod 有 ~18k 個 provider/clinicadmin v2_calendar `timezone='UTC'`**（VP-16202 migration 從 legacy `crm.clinician.time_zone` backfill，但 legacy 沒值的維持 UTC）。即便 #2 修了，這些 calendar 仍會落到 fallback `America/Los_Angeles`，對非 LA 的 clinician 仍是錯的。長遠要從 setting service / user profile 重新 backfill 或讓 user 自填。

對應位置：`LIS-transformer-v2/src/calendar/models/event/event.service.ts` 的 `resolveEventTimezone` + `formatDateInTimezone`，以及 `reminder/reminder.service.ts:217`（reminder 用 `recipient.timezone || event.timezone || 'America/Los_Angeles'`，跟 event email 走 provider tz 不同——故意：appointment 信以 provider 在地時間為主，reminder 以收件者本地為主）。

### kafkajs 連 Azure Event Hub（debugging 用）
```js
new Kafka({
  brokers: ['<namespace>.servicebus.windows.net:9093'],
  ssl: true,
  sasl: { mechanism: 'plain', username: '$ConnectionString', password: connectionString }
})
```

### Event Hub retention 容量決定論
高量 topic（如 `general-sample-events`）有效 retention 可能短於 7 天（VP-16413 撞到 4/24 才有最早留存，4/21 訊息已過期）。事後驗證得在事發後盡早做。

### LIS Kafka cluster 雙寫：on-prem `lis-general-events` ↔ cloud `general-sample-events`（VP-16784-87 verification 2026-05-28）
**已驗事實**：
- on-prem `lis-general-events`（`192.168.60.9-11:9095`，9 partitions）跟 cloud Event Hub `general-sample-events`（namespace `general-events`，host `general-events.servicebus.windows.net:9093`，1 partition）是**同一份 stream dual-published 到兩個 cluster**
- 同 4-hour timestamp-aligned 窗口 consume：cloud 22 條 `report_finished` / on-prem 37 條，**event_id 交集 8 / sample_id 交集 8 / accession_id 交集 8**；8 個 shared sample 的 event_id + millisecond timestamp 兩邊 byte-identical
- topic 名稱差距大（`lis-general-events` vs `general-sample-events`）容易誤判成不同 stream — 不要用名字下結論

**AKS→on-prem Kafka over VPN 也是 production pattern**（另一條路也通）：
- `ehr-chat/ehr-chat-configmap` 與 `ehr-workflow/ehr-workflow-configmap` ConfigMap KAFKA_BROKERS 寫 `["192.168.60.9:9095","192.168.60.10:9095","192.168.60.11:9095"]` 在 AKS prod 跑著
- AKS pod kcat 對 on-prem brokers `-L` metadata + `-C -o -1` 真實 consume 都通，`advertised.listeners` 回 `192.168.60.x:9095` 跟 bootstrap 一致 — 無 DNS 解析問題

**衍生規則**：
- LIS service 從 on-prem 遷 AKS，Kafka 兩條路都可：
  1. 留 on-prem brokers 走 VPN consume — code 不動，配置不變
  2. 改連 cloud Event Hub `general-events.servicebus.windows.net:9093` + SASL_SSL — 需 code 加 SASL/SSL（KafkaJS 加 `ssl: true` + `sasl: {mechanism: 'plain', username: '$ConnectionString', password: <conn string>}`）
- 因 producer 已 dual-publish，**consumer 端切換不需要 producer 端協調**（這推翻舊版「順便遷 Kafka 必失敗」的判斷）
- consumer group offset 跨 cluster 不 carry over：切換瞬間從 latest 開始，`fromBeginning: false` 的 consumer 漏的訊息 < 1 秒 production
- **Kafka 沒有 gRPC 的 per-call fallback**：consumer 是長連接訂閱，連哪個 cluster 就只收哪邊事件。`tryCloudThenOnPrem` 對 Kafka 不成立 — 但因兩邊內容等價（dual-published），「fallback」需求本身大幅減弱

**Verification 方法論教訓**（這次三度翻轉結論的根因）：
- 多 partition + 流量懸殊的 topic，**「最新 N 條」抓樣是 false negative 製造機**：cloud 1 partition × N 條 = 短 wall-clock 窗口；on-prem 9 partitions × N 條 = 各 partition 從各自 latest 抓 N/9，partition 不均時部分 partition 從昨天就停 production，wall-clock 窗口可能跨數小時到數天。兩邊窗口時間不重疊 → 自然 0 交集 → 誤判「不同 stream」
- 正解：`kcat -o s@<unix-ms>` **timestamp seek** 強制兩邊從同一 wall-clock 起點抓，才能公平比對
- `nc TCP OK` < `kcat -L metadata OK` < `kcat -C consume OK` < `event-id intersection (timestamp-aligned)` — 驗證深度排序，下結論要走到最深層

### Postmark Activity 查詢
UI → Server → Activity → filter recipient + template + date range。沒紀錄 = 訊息沒到 Postmark；有紀錄看 Status (Delivered/Bounced/Suppressed) 判斷下一步。

---

## Reminder Email — Cron + Audit Log Pattern (LIS-transformer-v2)

VP-16391 為 lab consult appointment reminder（48hr/24hr/15min）建立的 pattern。可重用於其他 transformer-v2 內的延遲觸發 email/notification 任務。

### transformer-v2 排程基建限制
- 無 Bull/BullMQ infrastructure（package.json 確認無 `@nestjs/bull` / `bull` / `bullmq`）— Bull 只在 `LIS-setting-consumer` 有
- 有 `ioredis` + `kafkajs`
- 既有 `EmailService.sendEmail()` 已支援 `delay` 參數，透過 Kafka topic `notification-email-template` 走下游
- 引入 `@nestjs/schedule` 即可加 `@Cron`，比引 Bull 輕

### C3 Pattern：cron + audit log table + atomic CAS
1. 新表（PostgreSQL `prisma/`）紀錄每筆 scheduled email：`scheduled_for` / `status` (`scheduled`/`sent`/`failed`/`superseded`) / `idempotency_key` (unique)
2. 觸發來源（如 event create/confirm）INSERT 多筆 reminder rows，`scheduled_for` 各自不同
3. `@nestjs/schedule` `@Cron` 每 30s ~ 2min 跑：`SELECT WHERE status='scheduled' AND scheduled_for <= NOW() + window` → atomic UPDATE → 'sent' → 呼叫 `EmailService.sendEmail()` → audit row 留存
4. **Reschedule**: source row 的 `start_time` 改 → UPDATE 舊 rows `status='superseded'` + INSERT 新 scheduled rows
5. **Cancel**: UPDATE all rows for source `status='superseded'`
6. **防重複**：`idempotency_key` unique constraint + atomic claim（`UPDATE ... WHERE status='scheduled' RETURNING ...`）

### 為何不用 Bull delayed job
- 跨 repo（setting-consumer）動 16K 行 controller 周邊太大
- transformer-v2 引入新 dep 測試複雜度高
- cron + log 表的 audit 性 + reschedule 處理（reset 欄位 vs removeJobs pattern）較簡單

### Schema 範本
```sql
CREATE TABLE v2_reminder_audit_log (
  id BIGSERIAL PRIMARY KEY,
  event_id INT NOT NULL,
  reminder_type reminder_type NOT NULL,
  scheduled_for TIMESTAMPTZ NOT NULL,
  status reminder_audit_status NOT NULL DEFAULT 'scheduled',
  idempotency_key TEXT UNIQUE NOT NULL, -- e.g. event_id + reminder_type + start_time
  dispatched_at TIMESTAMPTZ,
  ...
);
CREATE INDEX ... ON v2_reminder_audit_log (status, scheduled_for);
```

Migration 用 `prisma/manual-migrations/` + idempotent DO blocks（IF NOT EXISTS），手動 apply 到 prod schema（`scripts/<ticket>-apply-migration.js` 跑 raw SQL，不用 prisma migrate）。


## Cross-cutting RPC migration patterns（VP-16154 教訓）

### Helper pattern：把 secret/token plumbing 從 call site 抽離
大規模 RPC migration（OAuth2 metadata、auth header、tracing context）— 寫一層 helper 包 secret/token lookup，call site 只描述「我需要哪些 extra field」。好處：
- call site 不用 import secret，未來 cross-cutting policy 變動只需動一處（service-name 改名、internal_user_id=0 policy、required-field 規則）
- 易 mock：spec 只需 stub 一個 helper input/output
- 配合 strategy A（下方），整個 migration 變成 N 個 commit 每個都行為等同

VP-16154 例：`src/calendar/shared/rpc-metadata.helper.ts` 內 `buildRpcMetadata(setting, context, extraFields)` 包 `settingTool.createOAuth2Metadata`。calendar 7 個 service 全都 import 同一個 helper。

### Strategy A — Optional context migration（caller 不動，行為等同）
NestJS service 加 cross-cutting 需要 caller 提供新 context（例如 OAuth2 token info）時，三種策略：
- **B** 強制 caller 提供 → method signature break，N 個 caller 必須一起改，大 PR、爆炸半徑大
- **C** 拆兩個 method（authenticated / anonymous）→ 維護 N 倍 method
- **A**（推薦）method signature 加 **optional** context，caller 完全不動。`const metadata = context ? await buildHelper(...) : undefined`，RPC client 第二參數傳 metadata（undefined = 等同沒帶）

Strategy A 的優勢：**每個 commit 都行為完全等同**，可以一個 service 一個 commit 漸進 migrate，無需協調 caller 端。Phase 1a 全部 service 加 hook、Phase 1b 才 thread caller。回滾粒度小。

### Resilient helper > Strict helper（migration 期間）
Helper 包 token lookup / config 時，內部要 try/catch + return undefined，**不要 throw**。Caller 拿到 undefined 就 fallback 到原行為（RPC without metadata）。理由：
- migration 期間 token endpoint / secret 可能還沒 deploy 到所有環境
- 若 helper throw，整個 upstream method 跟著爆，違反「行為等同」承諾
- Logger.warn 留痕，misconfig 上線時看 log 抓得到

Strict validation 留到 migration 完成、所有環境穩定後再加。

### Pre-existing spec bug 的三種來源
加新 DI / 改 constructor 後 spec 突然爆 — 通常不是這次改造的鍋，而是 baseline 既有問題被掀開：
1. **TestingModule 缺 mock provider** — `providers: [..., { provide: NewDep, useValue: stub }]` 補上
2. **Spec 用 `new ClassName(args)` 直接 instantiate**（不走 DI），原本就漏 constructor arg（DI path 不會撞到、TypeScript 也不一定 catch 到，只有真執行才 error） — 加新 inject 順手補齊 args
3. **Spec expectation 跟 service 行為脫節**（service 有意改了 spec 沒同步） — `git log -S '<expected token from spec>' -- <service file>` 找出改動 commit，看 commit intent 決定改 service 還是改 spec。VP-16154 期間發現 clinic.service `contact_type === 'mobile'`（應該 `'phone'`）+ test 期望 auto-create calendar（VP-16146 有意拿掉）兩個 pre-existing bug 都是這條路徑找到的

### 找 schema 真相用 multi-site cross-check
同一個 field name / enum string 在 repo 多處被引用，若分歧（例如 7 處用 `'phone'`、1 處用 `'mobile'`）+ dto 註解明示允許值 → 多數 + 註解 = 真相方向。再加 production probe（read-only RPC call）驗證更穩。VP-16154 用這個方法確認 `contact_type` schema 是 `'phone'`，git log -S 確認 `'mobile'` 是 VP-16146 commit 打錯字串。

### Merge 後 typecheck 用 baseline 對照分離既有錯誤
合併大 branch (例如 feature → stage_test) 後跑 `tsc --noEmit` 常會看到一堆 error，若不知道哪些是 merge 引入、哪些是目標 branch 原本就有，會誤判 + 浪費時間。標準做法：
1. `git worktree add /tmp/baseline origin/<target-branch>`
2. `ln -s <main-repo>/node_modules /tmp/baseline/node_modules`（省 npm install）
3. 在 baseline worktree 跑同一道 `node_modules/.bin/tsc --noEmit -p tsconfig.json 2>&1 | wc -l`
4. 對照 merged-state 的 error 數量與檔案分佈。數量一致 + 檔案集合一致 = 全部 pre-existing，merge 無新引入錯誤
5. 用完 `git worktree remove /tmp/baseline --force` 清掉

關鍵：要用 repo local `node_modules/.bin/tsc`，不要 `npx tsc`（會跑到全域的 stub tsc 並印 "This is not the tsc command you are looking for"）。

### Merge conflict 的快速分類（VP-16154 ↔ stage_test 案例）
4 個 conflict 檔通常落入三類，先分類再決定解法可以省很多時間：
1. **Both-added imports / providers** — 兩邊各加自己的 module/service import，無重疊。解法：keep both（移除 conflict markers、兩段都留）
2. **Both-added constructor / mock args** — DI constructor 加新參數，spec 也對應加 mock。解法：keep both，但**順序要對齊真實 constructor 的 positional order**
3. **格式化 vs 語義變更** — 一邊 prettier 重排（無語義差異）、另一邊改函式簽章或加邏輯。解法：**採語義變更方**，格式化可後續用 prettier 重套

事前用 `git merge-tree --write-tree --messages <branch1> <branch2>` 做 dry-run 看 conflict 清單，不污染 working tree。

### SQL `COUNT(DISTINCT col)` 忽略 NULL — audit categorization 常踩（VP-16617 教訓）
SQL 規範下 `COUNT(DISTINCT col)` **不計 NULL**。對 audit 分類常造成「同一群 row 被誤判為 distinct 值較少」。

VP-16617 case：order_clients 有 87 個 (customer_id, clinic_id) 重複 combo。用 `COUNT(DISTINCT emr_name)` 分類時：
- combo (1044, 65) 有 [NULL, 'PF']
- SQL `COUNT(DISTINCT) = 1`（只算 'PF'）→ 分類為「same emr_name + diff kits」
- JS `new Set([null, 'PF']).size = 2` → 真正分類是「diff emr (one NULL)」

落差 84/87 combo，初版 merge script 全部走錯 pattern。

**修法二選一**：
- (a) JS 端用 `new Set` 重做分類（NULL 算 distinct）
- (b) SQL 用 `COUNT(DISTINCT COALESCE(col, '__NULL__'))` 強制 NULL 算一種值

**衍生規則**：audit 寫 SQL `COUNT(DISTINCT)` 之前先想「NULL 在這個 column 是不是有意義的 distinct 值？」是 → 加 COALESCE 或改 application-side 分類。

### LTM 內部矛盾時、優先 verify 對 authoritative source（VP-16617 教訓）
LTM 是 cached 結論，可能在不同段落寫互相矛盾的規則（VP-16617 case：emr-integration.md 行 173-176 mapping table 寫 `kits=0↔NON_BLOOD_ONLY`，但行 451-454 stub finalize default 寫 `kit_delivery_option=NO_DELIVERY + kits=0` — 兩條應該對齊，但實際不一致）。

**鐵則**：發現 LTM 兩處規則應該一致但實際不一致時，**先去找 runtime authoritative source 確認**（譬如 EMR-Backend Java `ParseHL7.java:930` switch case 是 runtime 真相），不要照其中一條規則直接動。當下修正 LTM 較舊或較弱證據的那條。

**判斷誰是 authoritative**：
- ✅ Runtime code (Java parser、TS service、SQL trigger) — 真實執行的邏輯
- ✅ Production data distribution + DB schema constraint — 直接觀察
- ❌ LTM 規則表本身（cached）
- ❌ 舊 STM Decisions 段落（草稿）

**衍生**：write LTM 時若涉及多處應該對齊的規則表（譬如 enum mapping），明確標 cross-reference 「此規則來源：`<file>:<line>` runtime code」，讓未來 reader 知道哪個是 source、哪個是 derivative。

### Dead vendor 數據會 bias audit 數字（VP-16617 教訓）
跑 prod-wide audit 找 misalignment 時，**先 filter 掉已知 dead vendor**（VP-16463 確認 PF 已死、不再進 order）— 否則 audit 數字會被殭屍資料灌水，分析失真。

VP-16617 case：
- 92 個 `kit_delivery_option` ↔ `kits_options` misalignment row：**91/92 是 PF**（dead vendor）
- 87 個 order_clients duplicate combo：**84/87 是 PF**
- 真實「活的」misalignment 只剩 1 row、duplicate 只剩 3 row

如果不 filter，看到「92 row 對齊問題」會誤估嚴重度、誤定 priority。

**標準 audit 流程加一步**：
1. `SELECT emr_name, COUNT(*) FROM <table> WHERE <issue condition> GROUP BY emr_name` 先看 vendor 分佈
2. dead vendor 占大宗 → 結論寫「N row total, M of which are dead vendor X (vacuous fix)」
3. 真正要動的 priority 看「活 vendor 的 N - M」

**Dead vendor 名單**（截至 2026-05-15）：
- PF (Practice Fusion) — VP-16463 確認停運
- BREATHERMAE — 後 historical 觀察

### Before adding a new field, check if existing free-form field covers the use case（VP-16474 教訓）
PM 開 ticket 要求「新增欄位、存進 DB、return 回來」時，**先評估能不能用既有 free-form field（如 `notes` / `description` / `metadata` JSON）裝這個資料**，不一定要動 schema。

VP-16474 案例：FE 想在 Clinical Consult Confirmation modal 顯示 provider name。ticket 寫 6 條 AC 要求 BE 加 `provider_name` 到 InputType / Event ObjectType / DB column / create + fetch endpoint。

考慮過 4 個方案後，pivot 到 **「encode 在 `notes` 字串裡」**，BE 完全不動 code：
- `notes` 已是任意字串、現有 FE encoding 已用 `[Key: Value]` envelope（e.g. `[Accession Id ...] [Phone: ...] [Meeting Type: Zoom]`）
- 只是延伸加一個 `[Provider: Tara Calmes-Norgaard]` entry，FE 自己 encode + parse
- Event GraphQL type 本來就 return `notes`、無需 resolver 變動
- 0 migration / 0 PR / 0 deploy risk

**評估「能否用 notes」的判斷準則**：
- ✅ 用 notes：純 display data、無 BE consumer（search / filter / report / audit / rule）、FE 一個 surface 用、有現成 encoding convention
- ❌ 用 notes：BE 需要 reason about（search / index / report key）、多 FE surface 各自 parse（脆 contract）、encoding convention 不在 README 之類有 documented 地方

**衍生規則 - 「不改 code」是 Step 4 user-discussion 的 first-class 選項**：Work Loop Step 4 提案時不要只列「實作 paths」，要把「BE 不動、FE/PM 換個角度解」列為其中一個 option。最便宜的正確答案有時候是 zero diff。

**核心心法 - 解碼 ticket 真實意圖（intent decode）**：PM ticket 文字常用 implementation language（"add a provider_name column"）描述 user-facing goal（"FE modal 顯示 provider name"）。**先把 ticket 的 user-facing goal 提取出來**再展開實作 path — 同一個 goal 通常有多種實作（add column / derive at read / encode in existing field / pure FE fix），其中最便宜的常常不是 ticket 字面方案。VP-16474 字面方案是「6 條 AC + 加 column + 動 5 個 file」、實際 goal 是「Confirmation modal 看得到 provider name」、最便宜方案是「FE 在 notes encode」zero BE。**先問「FE / user 為什麼要這個」，再列實作選項**。

### Temp hotfix 改 endpoint / config 用 hardcode，不要新增 env var
Leo 明確說「我自己會改回來」「臨時改一下」「先 revert」這類 temp hotfix 情境下，**直接 hardcode**，不要：
- 新增 env var（製造 deploy 時要記得 set 的負擔）
- 留 `// TODO LBS-XXXX` comment（Leo 自己會記得 revert）
- 加 feature flag（過度設計）

LBS-1487 案例：把 `process.env.VIBRANT_API_BASE_URL || '<wellness url>'` 直接 hardcode 成 local URL，完全 bypass env var。原因：prod 有 k8s configmap 設了 env var，改 fallback default 對 prod 無效；hardcode 才能在 deploy 後立即生效，且 Leo 之後 revert 也只要把字串改回去即 OK。

### env var fallback 預設值 ≠ prod revert
TS service 常見寫法：
```ts
const baseUrl = process.env.SOME_URL || 'https://default.com';
```
這個 `||` fallback **只在 env var 沒設時生效**。如果 k8s configmap / kustomization 已經把 env var 設成某個值，改 code 的 `||` 預設值對 prod **完全無效**。
要真正 revert prod 行為，二選一：
- (a) 完全 hardcode 忽略 env var（最強，prod 一定生效，但失去環境切換能力）
- (b) 改 `k8s/environments/<env>/kustomization.yaml` 的 env var 值（保留 env 抽象，但要走完整 deploy + configmap reload 流程）
LBS-1487 選 (a)，因為臨時 + Leo 自己 revert。

### Java field-initializer 預設值 不會 port 到 TS interface（v1→emr-v2 parity bug class）
Java model 常用欄位 initializer 帶預設：`private String token_platform = "stax";`。建 `new Foo()` 即帶這些值，呼叫端只 set 少數欄位。**port 成 TS `interface` 時這些預設消失**（interface 無 runtime 值）→ 若 construction site 沒明寫，欄位是 `undefined`，`JSON.stringify` 直接省略 → 送出的 request/payload 缺欄位。
- VP-16777：`TransactionPayInput` 6 個 Java 預設（token_platform="stax" 等），emr-v2 caller 沒帶 → charging API 缺 token_platform → 卡**靜默不收費**（無 error，最難抓）。
- **rule**：port 有 field-initializer 預設的 Java model 時，(1) 在 TS 做一個 `XXX_DEFAULTS` const、(2) **每個** construction site `{ ...XXX_DEFAULTS, ...explicitFields }`、(3) `grep` 所有 caller 確認都 spread 了（VP-16777 的 const 有建但 caller 漏 spread）。對接 v1→emr-v2 parity：「不能依賴 source default」「逐欄位 enumerate」。

### ⚠️ 嚴重失誤：絕對不要推測 staging URL / hostname / endpoint 命名
**2026-03-02 commit `52b347e` 引入的長期 bug**：Claude 幫 Leo 寫 swagger docs 時，看到 production 是 `www.vibrant-america.com/lisapi/v1/lis/emr-service/api/v1`，**直覺地按「web 通用 staging 命名」推測 staging 是** `staging.vibrant-america.com/lisapi/v1/lis/emr-service/api/v1`，寫進至少 4 份 docs：
- `docs/agent-enrollment-pipeline.md`
- `docs/vendor-inquiry-swagger.md`
- `docs/api/VP-12763-ordering-payment-swagger.md`
- `docs/api/ordering-payment-method-endpoint.md`

**真相**：`staging.vibrant-america.com` 從來不是 LIS staging gateway，那域名指向公司行銷 WordPress staging 站，**從沒人在那台機器設過 `/lisapi/*` proxy rule**。實際 LIS staging 慣例是**同 host + `-staging` 後綴**：
```
Production: www.vibrant-america.com/lisapi/v1/lis/emr-service/...
Staging:    www.vibrant-america.com/lisapi/v1/lis/emr-service-staging/...
```
（va-portal 用 `-st` 短後綴、emr-service 用 `-staging` 全名 — 命名不一致是歷史包袱，更需要查不能猜）

**下游影響**：FE 跟著 docs 抄，整套打到 `staging.vibrant-america.com` 都 404 + OPTIONS 405，看起來像 CORS error 但根本是 host 不對。debug 浪費**好幾個小時** trace CORS / gateway / ingress / WordPress，才回到 `git log -S` 發現是 Claude 自己幾個月前 commit 的 docs 推測錯。Leo 形容「嚴重錯誤」。

**鐵則**：寫 URL / hostname / endpoint / port / service name 進 docs 或 code 之前，**必須**：
1. **查既有 reference**：grep repo + 同公司其他 repo（va-portal/README、CLAUDE.md、staging k8s configmap），看別人怎麼寫 staging URL
2. **實測 curl**：對 staging URL 跑 OPTIONS + GET，看 server header、status code 是否合理（不是 nginx 預設 HTML、不是 405、不是 cloudflare 直接 reject）
3. **若無法驗證**：明確標 `<TBD: verify before use>` 或乾脆**不寫**，不要按 web 通用 pattern 推測填入
4. **「合理的命名規律」≠「事實」**：production 用 `www.` 不代表 staging 一定用 `staging.`。LIS 系統用同 host + `-staging`/`-st` 後綴；其他系統可能用 `api-staging.` 或 `stg.` 或 `*-st.*`。命名慣例**因系統而異**，每次都要查。

**寫 docs 時的判斷格式**：
- 我**知道**這個事實 → 寫
- 我**推測**這個事實 → **不寫** or 明確標「未驗證」or 先驗證再寫
- 「production 是 X，所以 staging 應該是 Y」**是推測不是知道**

寫 docs 的成本 5 分鐘、用戶 debug 錯 docs 的成本好幾小時，**精度遠比寫得多重要**。寧可 docs 缺一條 staging URL（留白讓人 ask），也不要填錯誤的 URL（看起來像權威 reference）。

### 單一 ticket vs umbrella migration scope（VP-16617 教訓）

**情境**：執行單一 integration ticket（如 VP-16617 Elation Harris 上線）時，常因 user 加 invariant rule（"oc 都要在 ei + ordering=1"）或 audit 觸發，發現大量 prod-wide drift（VP-16617 找到 366 row + schema 缺 unique constraint + dead vendor PF 還有 106+131 row）。

**鐵則**：
- **In-scope** = ticket 本身的可達成果（單一 integration LIVE + 直接 derive 的 invariant 對齊）→ 在 ticket 內完成、commit、close
- **Out-of-scope** = prod-wide audit findings、schema 缺陷、跨多客戶 / vendor 的清理 → 屬於 **EMR-Backend → lis-backend-emr-v2 migration umbrella**，**不**併入原 ticket，**不**貼到原 ticket comment
- **產出**：跨 ticket 的 findings 寫成 CSV / TSV 移到 migration 追蹤檔（命名不要含原 ticket ID，例如 `/tmp/emr-backend-migration-followups.csv`）
- **判斷標準**：「這個 finding 是否會在其他 integration 也出現？」是 → migration scope；只影響當前 customer/clinic → ticket scope

**為何**：Leo 強調 "已經不是這個 ticket 的範疇了"。Single-ticket 膨脹會混淆 ticket completion criteria、稀釋 audit findings 的能見度、讓 migration umbrella 沒有正確的追蹤位置。Ticket close 要乾淨，migration scope 要可累積。

**反例**（不該做）：把 Q1-Q6 PM questions 直接 comment 到 VP-16617 → Leo 拒絕，因為 VP-16617 已完成、那不是它的問題。

### 新增 send/recipient 邏輯時必須 diff against 同模組 reference impl（VP-16612 教訓）

**情境**：VP-16391 寫 reminder dispatcher 時漏抄 `event.service.ts:4098-4101` 既有 create-email 流程的 role filter (`role === 'provider' || role === 'clinicadmin'`)。結果 prod 跑了 2 週才被 PM 抓到 Clinical Team 也收到 reminder（VP-16612）。

**鐵則**：在 calendar / notification / messaging 模組新增「決定 recipient 的邏輯」前，先 grep 同模組既有 `send*` / `notify*` / `dispatch*` 函式，找出最相近的 reference impl，把 recipient 篩選條件**逐項對齊**（role filter、practice filter、status filter、email null check）。寫完 PR 前再對照一次。

**為何**：
- Recipient 篩選是 silent failure mode — 太寬不會 throw、不會 5xx，只會多發或少發 email，QA 不容易覆蓋。
- Reference impl 已經有人 review + ship + 跑過 prod，filter 條件代表「之前 PM 同意的最終語意」。新 code 不抄等於重新發明，且默默 diverge。

**最小檢查表**（每個新增 recipient 邏輯前跑一次）：
1. 同模組是否已有「同類事件、同類 practice」的 send flow？grep 找。
2. 該 reference 的 filter chain 包含哪幾條（role / practice / status / email null / blocked list）？
3. 新 code 每一條是否都 carry over？任何刪除/簡化需要明確理由 + Leo 確認。
4. Unit test 是否涵蓋「混合 role participants」「外部 practice 的 admin」「null email」「stale event」等 fixture？

### Jest test 必須對 shell `.env` 狀態免疫（VP-16612 教訓）

**情境**：reminder.service.ts 有 `if (process.env.platform_type === 'local') return;` early-return。VP-16391 寫 unit test 假設 jest 環境下 `platform_type` undefined → test pass。VP-16612 在 Leo 本地 shell（`.env` 有 `platform_type=local`）跑同一個 test → fail，因為 shell env 污染。

**鐵則**：任何讀 `process.env.X` 的程式碼，對應 unit test 必須在 `beforeEach` 明確 `delete process.env.X`（或 `process.env.X = expectedValue`）。**不要依賴 jest 環境下 env 是 undefined 的隱含假設**。

```typescript
beforeEach(() => {
  delete process.env.platform_type;  // ensure code under test doesn't early-return
  // ... other setup
});
```

**為何**：
- Jest 預設不載 `.env`，但 Leo 的 shell / direnv / Azure App Config 可能載入，造成 local vs CI 行為分歧。
- 「test pass on CI」+「test fail locally」是最浪費時間的 flake，root cause 通常 1 行 env state 差異。
- 在 `beforeEach` 顯式 reset 是 5 秒成本，省下「為什麼這個 test 在我這邊 fail」的反覆 debug。

### Recipient-targeted emails 的時間 format 預設 per-recipient（VP-16664 教訓）

**情境**：calendar 模組有多個 email builder（`event.service.ts` 8 個、`reminder.service.ts` 1 個、`meeting-request.service.ts` 3 個）會把 `event.start_time` format 成顯示字串放進 Postmark template model。VP-16391 寫的 `reminder.service.ts` 已 per-recipient（每個 recipient 用自己 calendar TZ format）；但 `event.service.ts` 是 outside-loop 計算一次 `eventTimezone = resolveEventTimezone(event)` 後給所有 recipient 共用 → patient 收到的時間其實是 provider TZ 的時間，看到 "10:30 AM" 不知道是哪個時區的。

**鐵則**：
- 任何發給特定 recipient 的 email，**時間 format 預設用 recipient 的 calendar TZ**，不要用 event/provider/server TZ
- 同一個 service 內若已有 builder 是 per-recipient（reminder.service.ts），其他 builder（event.service.ts）必須 align — 不一致是 silent bug
- `toLocaleDateString` / `toLocaleTimeString` **沒指定 `timeZone` option** 等同用 server process TZ（k8s pod 的 TZ）→ **絕不能用在 recipient-facing email**。改用 `date-fns-tz toZonedTime(date, recipientTz)` + `format()`。VP-16664 在 `meeting-request.service.ts:715-725, 301-311` 抓到 2 處既有 bug

**Display copy convention 細節**（VP-16664 確認）：
- **time / dateTime 字串**要帶 TZ abbrev（`"10:30 AM PDT"`、`"05/22/2026, 10:30 AM PDT"`）— recipient 才能不靠 paired field 就確認時區
- **純 date 字串不帶 TZ**（`"05/22/2026"`）— display copy convention 不寫 `"05/22/2026 PDT"`，看起來怪
- TZ abbrev 用 `Intl.DateTimeFormat({ timeZone, timeZoneName: 'short' }).formatToParts(date)` 拿，DST-correct（同個 IANA TZ 在不同月份會回傳 PDT/PST）

**Helper 範本**（已落地在 `src/calendar/models/shared/timezone.util.ts`）:
```typescript
export function getTimezoneAbbreviation(date: Date, ianaTimezone: string): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: ianaTimezone, timeZoneName: 'short',
    }).formatToParts(date);
    return parts.find((p) => p.type === 'timeZoneName')?.value ?? ianaTimezone;
  } catch { return ianaTimezone; }
}
```

**Refactor pattern**（event.service.ts 11 個 builder 適用）：
- 移除 outside-loop 的 `eventTimezone` + `formatted` 變數
- 進 recipient loop 後加：`const recipientTz = this.resolveRecipientTimezone(recipientCalendar, event); const formatted = this.formatDateInTimezone(date, recipientTz);`
- `formatDateInTimezone` 統一改成 `time/dateTime` 帶 TZ、`date` 不帶

### Upstream gRPC handler hang via Azure Redis NXDOMAIN（INCIDENT-20260518 教訓）

Azure Redis instance `vibrant-cloud-cache.redis.cache.windows.net` 從 K8s pod 的應用層**不可達**，多個上游 gRPC server (lis-core / lis-test-connect) handler 內 `await redisClient.xxx(...)` 永遠等不到 connection — 但 server process 仍 alive、K8s readiness probe 仍 pass。

對 emr-v2 (下游 client) 來說：

- **TCP 通 ≠ RPC 能跑** — server 收到請求進 handler 後在某個 Redis await hang，client 看到 DEADLINE_EXCEEDED 或卡到 deadline 超過
- **NodePort round-robin 行為分歧** — 兩個 pod 跑同 image，其中一個 ioredis 還持有 7 天前建立的 connection（cached state 還能用），另一個 cold-start 後就 hang。grpcurl 多打幾次會看到 50% OK / 50% DeadlineExceeded
- **`kubectl delete pod` 救不了** — 新 pod 起來跑同 image / 同 ConfigMap，會踩同樣坑
- **修法**：emr-v2 client 自己加 deadline + multi-tier fallback（v2 cloud primary / v1 on-prem fallback），不要等上游修。Cloud 版同 proto 註冊於 `10.224.0.199:30600` (testresult) / `10.224.0.199:30276` (referenceRange) / `10.224.0.199:32100` (coresamples sample/customer/patient)

**DNS 雙重狀態 gotcha**：`dns.resolve4()` 可能解到 IP，但 `net.createConnection(hostname)` 走 `getaddrinfo()` 仍回 ENOTFOUND。原因是 `getaddrinfo` 走 nsswitch + libc + `/etc/resolv.conf`，跟直接 DNS server query 不同 path。**Node application 用前者**，所以 application 看到 "Redis 不存在"，但 dns.resolve 又說有。debug Redis 連線時兩個都要測。

### emr-v2 result generation defensive layering（INCIDENT-20260518 教訓）

整個 `generateBatchResultsHl7` pipeline 任何 await 都不能 unbounded。三層防護缺一個都會被卡：

1. **Per-RPC deadline / timeout**：
   - gRPC client `client.xxx(req, metadata, { deadline })` 必設（30s for cheap calls, 120s+ for test results）
   - Node `fetch()` **預設無 timeout**，必加 `AbortSignal.timeout(...)`（PDF download 設 3min/attempt × 3 attempt）
   - SFTP 已有 60s connect / 90s ready，OK

2. **`tryWithBackup` helper**（`sample-test-result.service.ts`）：
   - cloud primary / on-prem backup
   - 觸發條件：DEADLINE_EXCEEDED (4) / UNAVAILABLE (14) / UNKNOWN (2) / INTERNAL (13) / client not initialized
   - 不在業務錯誤（NOT_FOUND 等）上 fallback，避免掩蓋 source bug
   - Step 1-5 都用同樣 pattern

3. **BullMQ outer hard timeout**（`result-generation.processor.ts`）：
   - `Promise.race(doProcess(job), 10min timeout)` 兜底，即使新加 un-bounded await 漏網
   - 配 `concurrency: 3`，一個慢 sample 不卡其他

**反 pattern**：catch fallback fabricate 假資料（如 `JB${sampleId}` 假 barcode + Unknown Patient）。發垃圾 HL7 到客戶 SFTP 比直接失敗還糟。**對外部依賴失敗，throw 比 fabricate 安全**，讓上層 catch 後 mark `GENERATION_ERROR` 等修。

### BullMQ worker hang ≠ stalled（INCIDENT-20260518 教訓）

BullMQ 5.x 的 stalled detector **只在 worker process 死掉（lock TTL 過期）才觸發**。如果 worker process 還 alive 但 handler 卡在某個 await，BullMQ 會持續 `extendLock`，job 永遠 active，後續 waiting jobs 無法被 fetch。

**檢查 queue 卡死**：
```bash
kubectl exec <pod> -c redis -- sh -c '
  echo "wait:    $(redis-cli LLEN bull:<queue>:wait)"
  echo "active:  $(redis-cli LLEN bull:<queue>:active)"
  echo "delayed: $(redis-cli ZCARD bull:<queue>:delayed)"
  echo "failed:  $(redis-cli ZCARD bull:<queue>:failed)"
  echo "completed: $(redis-cli ZCARD bull:<queue>:completed)"
'
# active 不變、completed 緩慢、waiting 累積 → worker hang
```

**看 active job 詳情**：
```bash
ACTIVE=$(redis-cli LRANGE bull:<queue>:active 0 -1)
redis-cli HGETALL bull:<queue>:$ACTIVE
# data → 看是哪個 sample，processedOn → 看 stuck 多久，progress → 看走到哪
```

**修法**：在 `process()` 包 `Promise.race` 加 outer timeout（10min for emr-v2 result generation；正常完成 <30s）。Leaked Promise 還在 event loop 但 worker slot 釋放，下個 job 可以跑。

**Recovery**：若已積壓，需先 dump `wait + active` 的 job data（含 sample_id + integration_id）到檔案，rollout restart pod（會 wipe sidecar Redis emptyDir），再 user 手動觸發補發。pending-resend list 撈法：
```bash
for ID in $(redis-cli LRANGE bull:<queue>:wait 0 -1; redis-cli LRANGE bull:<queue>:active 0 -1); do
  redis-cli HGET bull:<queue>:$ID data
done > jobs.ndjson
```

### lis-backend-emr-v2 gRPC endpoint topology（INCIDENT-20260518 教訓）

| 用途 | 主要 (default) | 備用 (cloud, in `tryWithBackup`) | 註冊的 service |
|---|---|---|---|
| Sample relevant info | v1 `192.168.60.6:30276` | v2 `10.224.0.199:32100` | `lis.SampleService` / `coresamples_service.SampleService` |
| listSamples | v1 同上 | v2 同上 | 同上 |
| getCustomer / getPatient | v1 同上 | v2 同上 | CustomerService / PatientService |
| Reference range (detailed) | v1 `192.168.60.6:30276` (lis-core, 卡 Azure Redis) | cloud `10.224.0.199:30276` 或 `10.224.0.236:5900`（後者 prod pod 路由不通） | `lis.ReferenceRangeService` |
| Test results detailed data | v1 `192.168.60.6:30600` (lis-test-connect, 卡 Azure Redis) | cloud `10.224.0.199:30600` ← INCIDENT-20260518 後改為 primary | `testresult.TestResultInfoGrpcService` |
| Self-exposed for manual retrigger | emr-v2 `192.168.60.6:31317` | — | `resultgeneration.ResultGenerationService` |

env var pattern：`GRPC_<SERVICE>_HOST` / `GRPC_<SERVICE>_PORT` (v1) + `GRPC_<SERVICE>_CLOUD_HOST` / `_PORT` (cloud) + `GRPC_V2_<SERVICE>_HOST` / `_PORT` (v2 coresamples)。

**陷阱**：`coresamples_service.*`（v2，port 32100）跟 `lis.*`（v1，port 30276/30600）是不同 package。同一 IP 不同 port 上跑不同 server process，各自 `server.addService(...)` 註冊不同 service。「TCP 通到對的機器」≠「對的 RPC 註冊在上面」。grpcurl error 區別：
- `Code: Unimplemented` (gRPC status 12) → server 真的回，service/method 沒註冊
- `target server does not expose service "X"` → grpcurl 本地從 proto 載入時拒，沒送到 server
- `service "X" does not include a method named "Y"` → 同上，本地 reject，通常 method 大小寫拼錯


### Calendar availability 回空 / off-grid slot 診斷（VP-16850）

LIS-transformer-v2 calendar 排程。`getProviderAvailability` (provider-availability.service.ts)：

**availability 回空時的排查順序（先查設定再懷疑邏輯）**：
1. `v2_calendar.max_advance_days`（schema `@default(30)`，line 177-184）：把 query 的 end_date 砍到 `今天+max_advance_days`。**用遠未來日期 query 必定回空**，day loop（`while dateString<=endDate`）一次都不跑。calendar 30791 設 28。
2. `v2_calendar.min_notice_minutes`：擋掉 `今天+min_notice` 之內的 slot。
3. 兩者都是 clinician/admin 經 GraphQL mutation `updateUserBookingRules` → `updateBookingRules()` 寫進 v2_calendar（不是 bug、不是 default）。同值在下單時由 `validateBookingTime` 二次 enforce。

**off-grid（:15/:45）slot 不顯示/不能 book**：`generateSlotsFromPeriods` 舊版用 `Math.ceil(min/30)*30` 把 period 起點對齊全域 :00/:30 grid，30 分鐘寬的 off-grid 窗口被推出 period.end 而整段丟棄。修法：錨在 `period.start` 逐 SLOT_INTERVAL 步進（on-grid 不變）。注意 `event.service.ts:generateScheduleAwareSlots` 有同一份重複邏輯（VP-16850 未動，另案）。

**真實重現/驗證法（read-only）**：`new PrismaClient({datasourceUrl})` 指 `schema=calendar_prod`，可直接 `new ProviderAvailabilityService(prisma, silentLogger, {})` 呼叫（getProviderAvailability 只用 prisma+logger，不需 onModuleInit/gRPC）。要跑「實際修改後」的行為就 require `dist/` 編譯產物。`.env` 的 DATABASE_URL_CALENDAR 有 dev_new+prod 兩份，dotenv 取後者=calendar_prod。calendar 30791 owner_id=46607（GraphQL input 的 provider_id 999997 是 resolver 另外 map 的，別拿來當 calendar_owner_id 查）。

### Booking 驗證統一閘門（VP-16850 Phase 2）

LIS-transformer-v2 calendar：customer 預約「能不能 book」要與「getLabClinicianAvailability 顯示什麼」一致，否則會出現 outside-availability。

**單一真相來源** = `ProviderAvailabilityService.validateSlotAvailability({clinicianCalendarId,startTime,endTime,excludeEventId?})`。涵蓋：is_active + TZ-correct `buildAvailablePeriodsForDay`（**無 9-5 fallback**，無排程當天=不可 book）+ `fitsInPeriod`（[start,end] 落在某窗口內）+ min_notice + max_advance + 單一event/recurring(rrule)/pending-request 衝突 + excludeEventId（reschedule 排除自己）。

**所有 customer 路徑都走它**：createMeetingRequest、public-booking.createAppointmentRequest、createEventByPatient、update、rescheduleClinicalConsult。**provider `createEvent` 不驗證**（刻意）。

**反例/已移除的 bug**：舊 `MeetingRequestService.isWithinWorkingHours` 用 `start.getDay()`/`start.toISOString()`（server TZ，非 calendar TZ）算星期/日期，且無排程時 fallback「9AM-5PM 可預約」→ 週末/未排程日可被預約 = outside availability。改 code 時若看到「沒排程就 default 9-5」幾乎一定是 bug。

**陷阱**：同一驗證邏輯散落多份（meeting-request 有一套、provider-availability 有一套），且 `isTimeSlotAvailable` 多做了 recurring(rrule) 衝突而 `validateSlotAvailability` 原本沒有——統一/替換前務必逐項比對兩套的涵蓋範圍（recurring、min_notice、max_advance），缺的要補進閘門再替換，否則靜默漏檢。

---

## Clinical Consult Reminder — 「Postmark 有寄但 prod DB 查無」的排查鏈 + 多環境共用 prod 寄信管線陷阱 (INCIDENT-20260608)

**症狀通則**：客戶/PM 回報「取消後仍收到 reminder（或收到不該收的 email）」，但 prod calendar DB(`calendar_prod`)查無對應 event、`v2_reminder_audit_log` 也查無該 recipient 的 row。

**關鍵認知：`prod DB 乾淨` ≠ `沒 bug`。** 會抹掉/繞過 prod 證據的兩大來源：
1. **`v2_reminder_audit_log.event_id` FK 是 `ON DELETE CASCADE`** — event 一被 hard-delete(`deleteEventByPatient` 的 `is_canceled=false` 分支),reminder 稽核紀錄連同 event 一起消失。audit log 本應在刪除後存活,這是 observability 缺陷。
2. **另一個「環境」直接 publish 到 *prod 的* notification Event Hub,卻不寫 prod 的 DB**。reminder email 真正寄出與否，看的是有沒有訊息進 `notification-email-template` topic，不是 prod calendar DB。

**多 transv2 部署都共用同一個 PROD 寄信管線（治理破口）**：
- `notification-email-template` @ `vibrant-notification-events.servicebus.windows.net:9093`(env var `Azure_notification_topic` / `Azure_kafka_notification_url`)被 **prod、staging、甚至 test 環境** 共用。對照組:appointment events 有正確隔離成 `general-sample-events-staging`,唯獨 **email topic 沒隔離**。
- reminder `@Cron`(`reminder.service.ts`,每 2 分)**只被 `platform_type==='local'` 擋**。任何 `platform_type≠local` + 讀到「有 due event 的 calendar DB」的 transv2,就會寄**真信給真客戶**。
- idempotency(`idempotency_key` UNIQUE)是**各 DB 各一張 audit 表** → 不同環境/DB 不互相去重。
- 已知環境：AKS `transv2/lis-transv2-deployment`(→`calendar_prod`)、`-st`(→`calendar_dev_new`)、on-prem `lis-calendar-dev`(另一套舊 `TasksService` app)、**AKS cluster `listest`**(見下)。

**隱藏的 `listest` cluster**：sub `4dbf30e2-...` / rg `lisportalprod` 有一個 AKS cluster **`listest`**,多數帳號(含 Leo)**無 Azure RBAC**(`az aks list` 會把它濾掉、`az aks show`/`get-credentials` 回 AuthorizationFailed,但 cluster 真實存在)。它曾跑 `lis-transformer-v2`(env=test、未 push 的本地 build)連 **prod** notification Event Hub + 讀**陳舊 calendar 資料**(prod 的取消沒同步過去 → event 仍 `is_canceled=false`)→ 對真 provider 持續寄真 reminder。**當 prod 證據缺失但 email 是真的,優先懷疑 `listest` / 其他 subscription 的 cluster。**

**Forensic chain（鎖定「是誰寄的」）**：
1. **Postmark Messages API**(server token 在 `noti/notification-center` pod env `POSTMARK_KEY`;`curl https://api.postmarkapp.com/messages/outbound?recipient=...` + header `X-Postmark-Server-Token`)→ 確認真的有寄、看 Subject/Metadata/MessageEvents、`/details` 看 body(consult_date/clinician 確認是哪場)。
2. **Kafka `notification-email-template`**(kafkajs,`$ConnectionString` SASL)consume 找那封 → 它的 message **headers 帶 dd-trace 注入的 `x-datadog-trace-id` / `traceparent`**(producer instrumentation)。payload 結構 = transv2 `email-template-config.service.ts buildEmailMessage`(`MessageID:uuid`、`Tag:calendar_${NODE_ENV}`、`TemplateId`、`TemplateModel`、`MessageStream:outbound`)。
3. **Datadog producer span**(用 trace id 查,站點 us3.datadoghq.com)→ 給出 `service` / **`env`** / `git.commit.sha` / **`host`**。`host` 是 node 名(`aks-agentpool-<id>-vmss<n>`)→ 比對 `kubectl get node` + `az aks list`/`az vmss list` 判斷屬於哪個 cluster。**span 沒有 `kube_*` 標籤 ≠ 不在 k8s**(可能是該 cluster Datadog 沒做 pod 標籤);用 `host` 才準。
- 還原**被刪 event 的 id**:`v2_event_accession_audit_log`(不隨主表 cascade 消失,記 claim/release + event_id + reason)+ Postmark email body 重建 lifecycle。

**止血手法**:在出事的 cluster `kubectl scale deploy <transv2> --replicas=0`,或改其 `Azure_notification_topic`/`Azure_kafka_notification_url` 為非 prod,或設 `platform_type=local`。**根因治理**:非 prod 環境不得持有 prod notification Event Hub 連線字串;reminder cron 在非 prod 一律 gate;test calendar DB 定期 refresh 或標記禁止對外寄信。

---

## 改一個「不變量」的語意 → 必同步同 scope 內所有它的衍生點;測試別 mock 掉相依路徑 (VP-17260, Bugbot 連抓 2 次)

**症狀通則**:一個概念/邊界在同一函式或 flow 裡常有**多處表達**(顯示值、驗證 cutoff、查詢窗、forward/backward search 上下界、下游計算)。只改其中一處的語意、沒同步其他處 → 它們開始不一致。`getBookingRules` 的「max-advance 預約上限」就被連抓兩次:
1. VP-17260 原始改動:`validateBookingTime` 改用 `maxAdvanceCutoff`(第 N 天結束/per-day),但 `getBookingRules.latest_bookable_time` 還是 rolling `now + N*24h` → **顯示 ≠ 驗證**。
2. 修 (1) 時:把 `latest_bookable_time` 對齊了 `maxAdvanceCutoff`,卻漏掉**同一函式上方約 10 行**的 schedule-exception 查詢窗仍用 rolling `maxDate` → 美國(UTC 負偏移)時區 cutoff 日可能晚一天,**最後一天的 closure 沒載入** → `calculateEarliestBookableTime` 可能漏看。

**根因**:只修「被指出的那一行」、在改動點做局部推理,沒先列出同 scope 內所有「表達同一概念」的點一起改。這是「migrate all readers, no mirror」/「audit callers when adding fallback」的同類,但範圍更小——**連同一個函式內**都漏。

**為何測試沒擋住(關鍵)**:Finding-1 的測試把 `v2_schedule_exception.findMany` mock 成 `[]`,等於把會出問題的相依路徑 mock 掉 → 綠燈是**假信心**。只測了輸出值(`latest_bookable_time`),沒測內部資料抓取窗口的一致性。

**做法**:
1. 改某值/邊界的**語意**前,grep/讀**整個函式 + flow**,列出所有「衍生自它」或「必須跟它一致」的點(顯示、驗證、查詢窗、search 上下界),同一 PR 一起改,並用**同一個 single source** 算(本例:`const latestBookable = maxAdvanceCutoff(...)` 算一次,顯示值與查詢窗都用它)。
2. 測試**不要 mock 掉與該不變量共用的程式路徑**;挑一個會真的踩到相依點的案例(如 rolling 日 ≠ cutoff 日的特定時刻),確認**舊碼 fail、新碼 pass**。

## FHIR endpoint 測試 token 取得法（FHIR-ONDEMAND-RESULT, 2026-07-02）

之後驗證 lis-emr-v2 FHIR endpoint（`/v1/report/fhir` → `/api/v1/fhir/DiagnosticReport`）都用這條：

- **FhirAccessGuard 要求**：RS256 簽章 + scope ⊆ {result, report} + live OAuth session。prod OAuth `JWT_SIGNING_ALGORITHM=HS256`，拿 RS256 access token 兩條路：
  1. client_credentials + accountType=CUSTOMER 強制 RS256；
  2. OAuth PR #40（2026-06-24 deployed `4d643c6`）：`/token` 支援 `algorithm=RS256` one-way upgrade form field。
- **唯一有 result/report scope 的 client**：Cloud Report Service（OAuth DB Client id 75, clientId `MGI5NWQ3YjctOWMxMC00MjZkLThmMzktM2U0ODkzNDU4ZmJj`, INTERNAL/CC）。secret 在 `LIS-Report/base-report-server/deployment/azure/k8s-secret.yaml`（⚠️ plaintext 進 repo — 安全隱憂，已列待跟 Leo 提）。
- 完整指令：`POST api.vibrant-america.com/v1/oauth2/token` body `grant_type=client_credentials&client_id=...&client_secret=...&scope=report result&algorithm=RS256`。

### 查 deployed 行為前先比對 image SHA vs repo HEAD（FHIR-ONDEMAND-RESULT 教訓）
本地 OAuth repo checkout 過時（missing PR #40）差點導出錯誤結論。查 auth／deployed 行為前先 `kubectl get deployment -o jsonpath image` 取 image 的 GIT_SHA，對照 `git log`；落後就先 pull 再推理。

### OAuth prod DB（Postgres `Auth0`）read-only 查詢
`kubectl get secret my-secret -n oauth` 取 `OAUTH_DATABASE_URL` + `/opt/homebrew/opt/libpq/bin/psql`。`Session` JOIN `Client` 可反查「誰在什麼時候用哪個 client 拿 token」。

### Dormant feature：DB-config gate + short-TTL cache（VP-17344 確立，接 VP-16463/VP-17312 的 flag-cutover 族）

新功能要「部署零行為差異、之後 Ops 手動啟用」時的標準做法：
- 開關放 **DB 欄位**（ENUM，DEFAULT = 舊行為），不是 env var——UPDATE 即啟用/rollback，不用重新部署；per-integration/per-row 粒度。
- 熱路徑不能每 event 查 DB → **短 TTL（60s）in-memory cache** 的 gate（先查「有沒有任何 row 開啟」，空集合時新路徑零成本 early-return）。
- gate 查詢失敗必須 **fail-CLOSED**：回空集合且不沿用 stale cache——新功能暫停、舊行為不受影響。注意「註解說 paused 但 code 留著上次的 cache」這種寫法是 fail-open，Cursor bot 在 VP-17344 抓過。
- 部署驗證標準：flags 全 default 時新舊 code 的查詢/行為 **byte-identical**（VP-17312 pre-merge zero-diff audit 的做法）。

### Stacked PR 陷阱：parent 先 merge，child 灌進 feature branch（VP-17408, 2026-07-14 實踩）
GitHub **不會**在 parent PR merge 時自動 retarget open child PR — 只有 base branch 被**刪除**才 retarget。#258 (base=staging) 先 merge、#259 (base=feature branch) 後 merge → #259 的 diff 進了 feature branch，staging 完全沒拿到，PR 狀態卻是 MERGED。靠事後 `git log origin/staging` 驗證才抓到，rescue PR #261 補救。
**紀律**：stacked PR 一律 child-first merge；或 parent merge 時勾 delete branch；或 merge 前手動把 child retarget 到最終 base。**每輪 merge 後必驗 `git log origin/staging`（或目標 branch）** — PR 顯示 MERGED ≠ code 在目標 branch 上。

### Port 時代的 parity 註解不是 ground truth（VP-17408, 2026-07-13）
emr-v2 是 Java EMR-Backend 的 port，code 裡大量「Java parity」註解 — VP-17408 實證其中至少一處是**錯的**（OBR-16 provider name 註解聲稱對齊 Java，實際 emit NPI^Last^First，legacy 是 NPI^First^Last，已修）。**查 parity 問題一律回 Java 原始碼或 legacy 輸出樣本比對，不要信 port 註解**。

### VP Jira Bug create 必填欄位（createmeta，2026-07-13/14 兩次確認）
VP project 的 Bug type 建單必帶（field id 以 2026-07-28 createmeta 重新確認，先前記載有誤植）：`Environment`=customfield_10492（Production/Staging/...）、`Impact`=customfield_10487（Extensive/Significant/Moderate/**Minor / Localized**）、`Portal Affected System/Page`=customfield_10082（single-select，EMR 選項 id=10639）、`Detection Method`=customfield_10489（Customer Report/Monitoring / Alerting/...）、`duedate`。Optional 但值得帶：`Bug Type`=customfield_10081（Code Bug 等）。Priority 名稱是 `"P0 - Highest"`..`"P4 - Lowest"`。RCA 欄位（結案時填）：`customfield_10485` Root Cause（rich text）、`customfield_10490` Root Cause Category（Code Defect / Configuration Error / Infrastructure / Process / Dependency / Requirements-Design / Insufficient Testing）。

### Staging 環境取數/測試技巧（VP-17286 E2E, 2026-07-13）
- **不用 VPN/DB 找 staging 測試病人**：portal staging API `GET https://api.vibrant-wellness.com/v1/portal/order/staging/orderTest/searchPatient?inputPatient=...`（dev-secret JWT，scoped by token customer）；`orderTest/patient?patientId=` 取完整 demographics。`allTests` 在 staging 是 404 — 測試代碼改查 prod Azure MySQL `package_price_mapping.uniqueemrcode`。
- **不用 VPN 查 emr-v2 staging DB**：`kubectl exec` 進 AKS staging pod，把 node script 寫進 `/app/temp/` 再跑 — `require('@prisma/client')` 從該目錄向上解析得到（放 `/tmp` 會解析失敗）。
- zsh 陷阱：shell loop 變數命名 `path` 會 clobber `PATH`（curl 直接消失）。
- ~~staging 已知 quirk：`generateBarcodeForSampleID` 對每個新 sample 失敗（Go upstream `unknown time zone America/Los_Angeles`）— 非致命（barcode best-effort），staging API order 無 julien_barcode 是預期現象，prod 健康。~~
  **【2026-08-14 dream 更新】此條已被 VP-17685 推翻兩次，不要再照抄**：(1) 根因是 coresamples **v2** scratch image 沒有 tzdata，barcode 已於 2026-08-12 21:51Z 改走 **v1**，這個 quirk 的成因消失了；(2) 「prod 健康」是錯的——同一支 RPC 在 prod 也是 100% 失敗，只是被非致命 catch 吃掉。**新狀態未知**：改版後 Datadog 對 `generateBarcodeForSampleID|julien_barcode` 查不到任何一筆（成功或失敗都沒有），沒有人做過 VP-17685 自己寫的驗收步驟。要用到 julien barcode 前先實際下一單看。
- **自鑄 emr-v2 JWT（HS256, JWT_SECRET）payload 必含 `userId`**（VP-17517 E2E, 2026-07-28）：JwtStrategy.validate 對缺 userId/user_id 的 token 一律回 generic 401 "Invalid token" — customer_id/clinic_id 齊全也不夠，錯誤訊息不會告訴你缺哪個欄位。
- **staging 的 order 資料活在 order-staging 自己的 DB，不在 .11 的 lis_core_v7**（VP-17517, 2026-07-28）：staging API 下的單在 lis_core_v7 查不到 ≠ 不存在；要證明 upstream 狀態，直接打 order-staging service（如 re-cancel 期待 409 "Order already canceled"）。
  - **【2026-08-07 VP-17628 修正／補充，以此條為準】「自己的 DB」不等於「拋棄式的 DB」。**
    staging pod `env=dev` → 下單確實打到 order-staging，但 **order-staging 與 prod 共用同一個
    order/sample store**：E2E 產出的 sample id（2554042/43/44）直接**接續 prod 的序號**。
    → **staging 下的單要當成真單處理：每筆用完必須 cancel**（VP-17628 三筆全部 patientPayLater
    + cancel，refund 0）。上面 VP-17517 那句只證明「在 `lis_core_v7` 查不到」，
    不能推論成「這是沙盒、可以隨便下」。
- **改 prod 資料來測 → 同一個 session 內改回去，並用「功能面」再證一次**（VP-17628, 2026-08-07）：
  為了測 clinic-only token 走 defaultProvider，把 clinic 153881 的 `clinic_setting.defaultProvider`
  由 `''` 暫設為 `'50658'`（用 transformer 的 `CreateOrUpdateClinicSetting` 原樣 shape，
  不要手寫 INSERT），測完改回 `''`。**還原的驗收不是「read-back 值對了」就算**——
  再打一次 API 確認行為回到 `422 default_provider_not_configured` 才是真的還原。
  收尾要能講出「零殘留」：3 筆 order 已 cancel、setting 已復原、兩種證據各一。
- **staging JWT_SECRET 在 `lis-emr-v2-config.yaml` 裡是 UNQUOTED**（VP-17628）：自鑄 HS256 token 前
  照抄時容易連引號一起帶進去。自鑄 token 的好處是能自由控制 scope 形狀（scoped / clinic-only /
  scope-less），unit test 蓋不到的 matrix 才測得出來；但 **scope-less service token 測不了** ——
  自鑄的 service-claim token 會在 `JwtAuthGuard` 的 data-access 層就 403，根本進不到 controller。
- emr-v2 對外 POST endpoints（/orders、/order-cancel）成功回 **HTTP 201**（Nest POST 預設），不是 200 — 寫 doc/Confluence 時照 201 寫，別照直覺寫 200。

### Consult reminder 兩個 producer 並存 — Postmark tag 指紋 + Bull replay class（VP-17421, 2026-07-15）
Prod 有**兩條**會寄 consult reminder 的管線，排查「不該收到的 reminder」先用指紋分辨是哪條：

| | transv2 dispatcher（健康） | legacy Bull processor（VP-17421 肇事者） |
|---|---|---|
| Postmark Tag | `calendar_prod` | `CustomerEventReminder`（template 33802989） |
| Subject 用語 | "in in N hours"（小寫） | "See You in N Hours"（大寫 Hours） |
| 稽核 | 每寄一筆寫 `v2_reminder_audit_log`，2-min cron 分批 drip | **不寫** calendar_prod 任何表 |
| 所在 | LIS-transformer-v2 | **LIS-transformer** `src/calendar/email/reminders.processor.ts`（從已 ARCHIVED 的 Portal-Calendar 遷入）；Bull queues `reminder_24h/48h/15m` 在 on-prem redis `192.168.60.9:4646`，由 `lis-trans-deployment-st`（stprod）pod 消費 — **stprod pod 寄真 prod email**，VP-16921 同款 design smell |

快速判別法：**Postmark 筆數 vs `v2_reminder_audit_log` 同時窗筆數**不符（如 338 vs 1）→ burst 不是走 prod dispatcher。Postmark 查詢用 `tag=` exact（`recipient=` filter 不可靠、subject search 會漏；token 在 noti/notification-center pod `POSTMARK_KEY`）。VP-17422 再驗證同手法：**筆數算術直接指認 producer 執行次數**——30 msgs = 10 recipients × exactly 3、全部同 3 秒內 → `generateAndSend` 跑了 3 次 = 3 replicas 各跑一次；「exactly N×每 weekday」= 結構性（lock 從不 dedup），intermittent 才是網路 blip。先數 email 再讀 code，定位快很多。

**Bull delayed-job replay class**：delayed job 無 `removeOnComplete` 會在 redis 累積；`delay<0` guard 只在 **enqueue** 端，processor 端只查 `deleted=0` 不查 event 還在未來 → redis reconnect / pod restart 時 overdue jobs 整批 replay，對「早已過期的 event」照寄（VP-17421：restart 後 ~2min 爆 338 封、149 人、含 2025-03 的 event）。**紀律：時間敏感的 delayed/scheduled job 必須在 fire time 重驗前置條件（event 仍在未來）**，enqueue-time guard 擋不住 replay。Fix = LIS-transformer PR #562（processor 加 future-date guard）。

排查紀律（VP-16921 → VP-17421 實踩）：
- **不要繼承上一張 ticket 的 root cause** — 症狀長得像 VP-16921（stale reminder）但機制完全不同（rogue 環境 vs Bull replay）。舊 STM 該讀，結論要重新驗證機制。
- **restart 時間相關 ≠ 因果** — portal-calendar pods 正好在 burst 時間重啟而被誤指，但它們的 Bull 根本連不上 redis（無 REDIS_URL）。定罪前先證明嫌疑 service 真的持有那條 queue（去 redis 看 key 歸屬）。

### Rolling update 的完成判準 — deployment.status.readyReplicas 會算到舊 pod（VP-17497, 2026-07-27）
「deployment spec image 已更新 + readyReplicas>=1」是**假完成訊號** — rolling update 期間 readyReplicas 計入仍在跑的舊 pod，對舊 code 跑 E2E 白費 30 分鐘。正確判準：**找到 image == merge sha 的那個 POD，且它自己的 `containerStatuses[0].ready==true`**。同場加映：rollout 中途曾讀到一個從未存在的 bogus image sha（transient），單次讀值不可信，要重讀確認。

### 手動 repush/gRPC 迴圈要 pace（>=8s）— lis-core v1 burst 降級（VP-17493 backfill, 2026-07-27）
對 prod 快速連續呼叫 GenerateResultHl7（in-pod gRPC localhost:5000）：3 次成功後**每一發都失敗**（upstream `13 INTERNAL Error serializing response ... customer_name` ×12、`listSamples empty` ×2），幾分鐘後單發 probe 又全部健康 → burst 誘發 lis-core v1 gRPC（長期 Azure-Redis-bound 的那個 service）transient 降級。**手動批次 repush 迴圈固定 >=8s 間隔**；8s pacing 重跑 14/14 全過。另：sandbox 到 60.6:31317 不通時，in-pod gRPC（dist/proto + @grpc/grpc-js 寫進 /app/temp/）是免 VPN 路徑。

### Confluence 寫入：MCP 沒有 write 工具，走 REST v2 + JIRA_API_TOKEN（2026-07-27）
Atlassian MCP 只有 Confluence 讀取工具。要更新頁面：`.env` 的 `JIRA_API_TOKEN`（同一個 Atlassian token 兩用）直接 PUT Confluence REST v2（`/wiki/api/v2/pages/{id}`，body 帶 version+1）。VP-17497→17500 arc 用此法把 2485977089 推到 v15。

### 對外 API 的 doc 問答是 defect 探測器；doc 常領先 code（cross-ticket: VP-17497/99/500, 2026-07-27）
一天內 idempotency 語意改三次，每一層 defect 都是「回答使用者/PM 的 doc 問題」時暴露的：sandbox 行為 vs doc 不符 → reclaim（17497）；「客戶怎麼填 placerId」→ 查 uniqueness 作用域發現全域 unique（17499）；optional 需求 → 17500。**認真回答 doc 問題（對 ground truth 查證，不是照 doc 復述）= 便宜的 defect 掃描**。同 arc 的第二個教訓：這個 repo 的 doc 慣性領先 code — ORDER-PIPELINE.md §2.6「承諾」了 payment replay 但沒實作、Confluence spec 也常領先 impl；**doc 說有的行為要當 claim 驗證，不當事實**。同 arc 第三個教訓：defect-found-must-be-ticketed 規則連續兩次在同 session 立刻執行（VP-17499、VP-17503），流程有效。

## 【PROMOTED 2026-07-29】部署驗證的終局判準：exec 進 pod grep dist 內容（4+ 案例跨 ticket 蒸餾）

「code 到 prod 了嗎」這個問題被連續四次答錯，每次錯在不同的代理指標上。收斂成一條規則：

**唯一可信的判準 = exec 進當前 pod，grep 編譯產物（`dist/`）裡那個變更專屬的字串。** 找不到就是沒上線，不管其他訊號多綠。

已知會騙人的代理指標（每一條都真的騙過一次）：

| 代理指標 | 為何不可信 | 案例 |
|---------|-----------|------|
| PR merged + GitHub Actions deploy `success` | GH Actions ≠ 實際部署；Jenkins 才 apply，今天實測落後 ~2h | VP-17531 |
| pod image tag == merge sha | **Jenkins 用觸發 commit 打 tag，但 build 的是當時的 branch HEAD** → tag 與內容雙向都可能不符（實測 image 標 bacfb1c/#300 卻含 #301 的 code） | HL7FAIL-20260729 |
| `deployment.status.readyReplicas >= 1` | rolling update 期間會算進還在跑的舊 pod | VP-17497 |
| 單次 `kubectl get pod` 讀值 | **phantom read，已 2 次**：讀到 pod「Running true <sha>」，事後連 ReplicaSet 都查無此物 | VP-17497, VP-17531 |
| 本地 repo checkout | 落後 origin 就會推出錯結論 | FHIR-ONDEMAND-RESULT |

衍生紀律：
- **「先確認 code 有沒有真的在跑，再 debug code」** — VP-17531 差點去修一個不存在的 Nest bug（`@Controller(['a','b'])` 陣列路徑在 v11 本來就合法，404 的真因是 deploy 沒發生）。
- **對外 API 的 404 vs 401 是零副作用的 route 探針**：401 = route 通、服務在驗 token；404 = route 斷。prod 驗路由不需要碰任何真訂單/真資料。
- 報「prod 還沒有這段 code」之前先 `git log origin/main` 確認有沒有 promotion PR — promotion PR 標題常沒有 ticket id（VP-17531 漏看 #298，Leo 一句話抓到）。

### Config store 沒有歷史 ≠ config 沒變過（VP-17532, 2026-07-29）
P1 報「booking 落在我的 availability 之外」，engine 其實正確：**資料寫入時的 config 與現在的 config 不同**。`v2_schedule` 沒有 timestamp/history，但 `updateWorkingHours` 是 `deleteMany + createMany` → **該 calendar 的 row id 是全表最大值，就證明它的 weekly hours 比所有其他 calendar 都晚被重寫**，晚於最後一筆爭議 booking。
- 通用紀律：**診斷 engine bug 前，先確認「資料違反的那份 config」在資料寫入當下是否存在**。
- 通用技巧：**delete-and-recreate 的寫入模式讓 surrogate key 順序變成可用的「變更時間推定工具」** — 沒有 audit table 也能定序。
- 排除法紀錄（避免重走）：pooled multi-clinician slot 洩漏（VP-16499）被 participant signature 排除（`clinicadmin/no_response + patient/accepted` = `createEventByPatient` legacy path，不是 reschedule — reschedule 會留 cancelled twin，一個都沒有）；timezone 理論被 live 查 core SettingService gRPC 排除（她的 tz 自 6/24 起是 America/New_York，任何 tz 解讀都無法讓那些時間通過 `validateSlotAvailability`）。
- 產品缺口（Leo 決定不開票）：縮小 weekly hours 時，既有的未來 booking 不會被重新驗證，也不會通知任何人。

### 權限檢查鏈的超時預算會變成 UI 卡死（PO-256, 2026-07-29 oncall）
Accessioning「送不出 tube count、轉圈轉到底」的完整鏈：LIS-frontend `UpdateTubeInfoDialog.vue` → LIS-Shipping（AKS `lisportalprod` ns `shipping`）`OrdersTubesService.receiveTubes` → `PermissionGuard` → `CheckPermission` gRPC → coresamples-v2（ns `coresamplesv2`, Go）→ **RBAC Container App（Azure Container Apps，每 call 5s timeout）**。
- RBAC Container App stall 15 分鐘（DeadlineExceeded）→ shipping 在 ~17s 後回 403（≈3 retry × 5s + overhead）→ 35 個請求被擋（22 筆 tube receive、12 筆 phlebotomist patch）。**UI-blocking 的 guard 給 17s 預算太長，該 fail-fast。**
- 前端把 403 變成無限轉圈的機制：axios throw → catch 回 `undefined` → caller 讀 `res.data.code` → TypeError 逃出所有 try/catch → `changeLoadingState(false)` 永遠不執行。**「錯誤處理」catch 完回 undefined 而不 rethrow，等於把可診斷的失敗變成不可診斷的凍結。**
- 診斷紀律：pod 全健康（無 restart、無 deploy、無 error burst）+ 錯誤字串指向下游 → 責任在下游的 managed service，不要在健康的 service 裡找。`az` MFA 過期就明說查不到，把邊界標清楚（Azure Container Apps 是 platform team scope）。

### Cross-ticket review 2026-07-29（marker 2026-07-27 後 7 張 completed：VP-17517, BETA-E2E-20260729, VP-17531, VP-17532, VP-17533, PO-256, LBS-1674）
三個系統性 pattern：

1. **「code 到 prod 了嗎」是這批 ticket 的最大共通線** — 已升級成上面的 PROMOTED 章節（4+ 案例、5 種假訊號）。這族從 2026-07-22 的「status 不是 ground truth」一路長到「連 image tag 都不是 ground truth」，現在的終點是 dist 內容。
2. **scope 邊界規則一天內 5 次全部執行正確**（`defect_found_must_be_ticketed`）：別人的 service 只交診斷不自己開票 — PO-256（RBAC Container App，platform team）、HL7FAIL-20260729（BestDeal，order team）、VP-17537/17538 附帶發現的 charging ACH bug、BETA-E2E 的 QA client OAuth 500（Rust OAuth 服務）；自己 scope 的立刻開票 — VP-17531、VP-17537。**規則已穩定，不需要再蒐證**；剩下的風險是反向的：交出去的診斷沒人追（BestDeal 至今未修，靠 VP-17535 workaround 撐著）。
3. **interim workaround 不可 hardcode 會漂移的值**（Leo 2026-07-29 兩次退回 VP-17535 設計）：第一版打算回傳 synthetic BestDeal response 含固定價格 → Leo 指出「價格會變，hardcode 會壞」。最終版改成**把 bundle 拆成 component test id 塞進同一個真實 request，response 原樣通過** = 定價永遠是 live 的。**臨時方案的判準不是「多快能上」，而是「它會不會靜默地過期」**；同時 workaround 必須配一張移除追蹤票（VP-17535 本身）。

## 跨 cluster 消費者切換：rollback 不是 cutover 的鏡像（VP-17559/17561, 2026-07-31 dream 抓到）

emr-v2 的 result consumer 從 on-prem Kafka 切到 cloud Event Hub，71 分鐘後被 `KAFKA_CLOUD_ENABLED=false` + rolling restart 切回去。切過去健康、切回來卻**重送了已投遞的結果**。

- **機制**：兩個 cluster 是 dual-publish（同一批事件都在）。consumer group 的 committed offset 是**每個 cluster 各自一份**。切走的那一刻，舊 cluster 的 offset 就凍結在那裡；切回來時 `fromBeginning:false` 不救你 —— 它是從**凍結的 offset** 續讀，於是把切換視窗內的每一則事件重新消費一次。
  - 正向（cutover）= **gap**（新 cluster 從 latest 開始，切換瞬間的訊息永不消費）——這個大家都會寫進 caveat。
  - 反向（rollback）= **overlap**（整個視窗重播）——這個通常沒人寫，因為 rollback 被想成「回到原狀」，但 offset 不會跟著回到原狀。
- **紀律**：切換計畫要同時定義兩個方向。丟一個進去：(a) rollback 前把舊 cluster 的 offset 前推到現在（offset forwarding），或 (b) 投遞端有 idempotency gate。**兩者都沒有就不要切**，因為 rollback 是出事時唯一的手段，而它本身會製造事故。
- **一般化**：任何「同一份資料流有兩個獨立進度指標」的遷移（cluster、佇列、CDC slot、cursor table）都有這個不對稱性。判準問題是「回切時，舊來源的進度指標指在哪裡？」
- **偵測手法**：不要只看「有沒有新增 row」。重播可能命中「重用既有 record」的路徑，於是 row 數不變、只有 `updated_at` 前進。查 `updated_at > created_at`（或 > 切換時間）才看得到，配合 app log 的 reuse 訊息。這次 row count 完全正常，17 筆重送全靠 `updated_at` 才浮出來。
- **同時學到**：ConfigMap 的 `metadata.managedFields[].time` + `manager`（這次是 `kubectl-patch` @ 01:35:13Z）是「誰在什麼時候改了 config」的 ground truth；deployment 用**同一個 image tag** rolling restart 就能改行為 —— 所以「image tag 沒變」不代表「行為沒變」（和 PROMOTED 章節的「tag 不是版本證明」是同一族，方向相反的那一半）。
- **後續（2026-08-01 dream 查證）**：01:35Z 切回 on-prem 之後，**02:16:20Z 又被 `kubectl-patch` 切回 cloud**（`emr-v2` ns 的 configmap），pod 自此連續 Running 47h、0 restart、SFTP `189 successful / 0 failed`、error 0 —— cutover 目前是**成立的狀態**，不是停在 rollback。第二次切換（on-prem → cloud）**沒有引發第二波重播**：`updated_at ∈ [02:16Z, 04:00Z] AND created_at < 02:16Z` 只有 3 筆，而背景基線本來就約 1 筆/小時 → 那 3 筆是背景。
  - **關鍵在於「為什麼沒有」：re-enable 之前先把 cloud group 的 offset 前推過 8,501 則堆積訊息**，也就是本節「紀律」條列的 (a) offset forwarding 被真的執行了。這是**這條規則第一次有正向證據**：同一個系統，沒做 offset forwarding 的那次切換重送了 17 筆 ORU，做了的那次 0 筆。
  - ⚠️ 不要把它誤讀成「視窗短／低量所以裸切安全」。cloud 端當時堆了 8,501 則待消費訊息，量一點都不小；差別是措施，不是運氣。
- **踩到的坑：同名 ConfigMap 存在兩個 namespace**。`lis-emr-v2-config-prod` 在 `default` 和 `emr-v2` 兩個 ns 都有（`default` 那份最後被改是 2026-06-17，早就不是活的）。不加 `-n` 查到的是 `default` 的殘骸，值可能剛好一樣而給出「已驗證」的錯覺。**驗 config 前先確認跑著的 deployment 在哪個 ns**（`kubectl get deploy -A | grep <svc>`），再對那個 ns 查。

### Cross-ticket review 2026-07-31（marker 2026-07-29 後 5 張 completed：VP-17559, VP-17561, VP-17538, VP-17539, VP-16934）

這批的共通線不是技術，是**「Jira Done 被當成流程的第一步而不是最後一步」**，而且比前幾晚嚴重一級：

1. **前幾晚的失效模式是「Done 但沒驗證」，今晚出現「Done 之後 prod 反向走掉」。** VP-17561 在
   17:27 PT 轉 Done，18:35 PT 被 `KAFKA_CLOUD_ENABLED=false` 切回去 —— 若 closeout audit 在 17:30 跑，
   它會**正確地判 PASS**，然後一小時後這個 PASS 就過期了。
   → 紀律：**closeout audit 的結論帶時間戳，不帶保證期**。對「靠 config flag 生效」的變更（不是靠
   image 版本），PASS 之後 config 還可能被改，所以這類 ticket 要記下「生效條件是哪個 flag」，
   下一晚重新確認那個 flag 而不是重新確認 deploy —— deploy 早就成功了，flag 才是真正的開關。
2. **票寫得很好，但驗收條件不會擋住 transition。** 五張裡有三張，「能證明它成立的那件事」就寫在票上
   卻沒做：VP-17538 的 priority order（票上明寫 "before this is considered final"）、VP-17539 的
   六個 bundle 各下一單對價、VP-17561 caveat 1 的重啟後 spot-check。缺的不是知識，是
   **acceptance criteria 與狀態轉換之間沒有連結**。可行的最小補強：轉 Done 前把每條 AC 逐條標記
   done/unmet/waived，unmet 的要寫理由 —— 這件事只有寫票的人做得到，不是 reviewer 能補的。
3. **「臨時方案要配移除追蹤票」的規則有它自己的失效模式**（2026-07-29 剛立的規則）：VP-17539（永久解）
   轉 Done，但實際上線的 code 仍掛著 VP-17535 的 `TEMPORARY` 標記與 log 前綴，而 VP-17535 仍是
   `Dev To Do`、移除條件寫著「BestDeal 回 200 就刪掉這段」。**永久票關閉時沒人回頭撤掉臨時框架**，
   於是留下一段「按註解指示就會刪掉生產定價邏輯」的 code。
   → 補強：workaround 轉正時，**同一個 commit 要一起拔掉 TEMPORARY 標記並關掉 removal tracker**；
   或反過來，永久票不要在 code 還標 TEMPORARY 時關。
4. 唯一乾淨的一張是 VP-16934（Epic，無 code 無 deploy）—— 也就是說**這批只有「沒有東西可驗」的那張
   通過得毫無爭議**，其餘四張都需要 audit 補證據。

### Cross-ticket review 2026-08-14（marker 2026-08-09 後 5 張 completed：VP-17651, VP-17653, VP-17685, VP-17691, VP-17715）

上面 07-31 那批的結論是「Done 被當成流程的第一步」。這批**同意那個結論，但把預測因子換掉了**——
真正能預測一張票會不會乾淨結案的，不是票寫得好不好、也不是變更大不大，而是
**工作進行中有沒有一份活著的 STM**。

把五張按「STM 何時存在」排開，結果是單調的：

| ticket | STM 何時寫的 | 結案品質 |
|---|---|---|
| VP-17715 | **工作進行中即時寫**，agent 自己走完 chain 才轉 Done | 唯一全綠：merge→DDL→2-signal deploy→prod E2E→config flip→Done，全部有證據 |
| VP-17651 | 工作中有，closeout 分多晚追加 | PASS，但 audit 推翻了自己前一晚的因果判讀（19.8s 499 是 OOM 的受害者，不是 proxy timeout） |
| VP-17653 | 工作中有 | 自己 PASS，但**順手抓到同批的 VP-17657/17658 在 Jira 是 Done、code 一行沒動** |
| VP-17685 | **事後由 closeout audit 補寫** | Done 比修好的 commit 早 60 秒；票上自己寫的驗收步驟從未執行 |
| VP-17691 | **完全沒有**，兩晚前就被 dream 點名，仍然沒補 | 只能在兩天後由 audit 從 Jira + PR 反向重建；至今沒有任何 live probe |

三條可以直接拿來用的推論：

1. **STM 不是工作的紀錄，是工作的一部分。** 沒有 STM 的票，缺的從來不只是記憶——
   VP-17691 缺的是「還有哪些 AC 沒做」這件事本身沒有任何地方在追蹤。
   事後補寫的 STM（VP-17685）可以還原事實，但**還原不了當時該做而沒做的那個決定**。
2. **唯一乾淨的那張，是 agent 自己按 closure chain 逐項驗完才轉 Done 的那張。**
   對照 07-31 那批「唯一乾淨的是沒有東西可驗的 Epic」，這是一個實質的進步：
   VP-17715 有 DDL、有 deploy、有 config flip，全部驗過。
   → 所以問題不在「chain 太難走」，走得完；問題在**誰按下 Done 的那一刻有沒有在走 chain**。
3. **closeout audit 的產出有一半是別人的票。** VP-17653 那晚抓到的是 VP-17657/17658，
   今晚抓到的是 VP-17691——兩次都不是被 audit 的那張票有問題，是**同批一起被轉 Done 的鄰居**。
   → 紀律：audit 一張票時，把**同一個時間窗內一起 transition 的票**都拉出來看，
   批次轉 Done 是個獨立的風險訊號，跟票的內容無關。

## Agent repo 自身的環境陷阱（2026-07-31 MiniLM 清除 arc 蒸餾）

- **驗 dream / memory pipeline 相關的東西一律用 `/usr/bin/python3`**：launchd 的 dream job 跑的是 system
  python（有 `rich`），homebrew 的 `python3` 沒有。用錯 interpreter 會得到與實際排程不同的結果 ——
  「我在 shell 裡跑過了」不等於「排程跑得起來」。
- **刪 config 欄位要直接 `import` 那個 module 來驗，不要跑上層腳本**：移除 `vector_store_path` 時漏刪
  `config` 裡 `field_validator` 的欄位名 → `import src.config` 直接炸 PydanticUserError，但 merge 前的
  驗證跑的是 `eval.py`，而它對 config 是 **lazy import**，那次執行根本沒觸發 → 假陰性，merge 後才爆
  （hotfix PR #18）。一般化：**驗證要直接觸發最脆弱的那一點**；「跑一個會用到 X 的程式」在 lazy
  import／條件分支下不構成對 X 的驗證。
- 退役決策寫進 README 有複利：這次「MiniLM 還會不會用到」的問題，README 早已記載退役理由與
  English-only 弱點，30 秒就定方向。

## 【家族蒸餾 2026-08-04】「某環節看起來正常，但沒驗證它真的在做我以為的事」

一天內同一形狀踩了四次（VP-17544 + VP-17591）。既有的 line 17（安靜的觀測窗）、line 51
（grep 範圍）已記過兩種變體，但沒能救我 —— 因為當時沒把它們當成**同一個 family**。
四個變體，判準都是「打開它真正的輸出/來源看一眼」：

1. **`void somePromise()` 丟棄的是回傳值，不是 rejection** —— unhandled rejection 讓 Node
   結束 process，於是一個「失敗也不該影響主流程」的告警旁支反而會殺掉服務。
   → 不 await 的 promise 一律 `.catch()`。（是自己寫的測試 `mockRejectedValue` 讓 jest worker
   crash 才抓到。）
2. **搜尋 flag 用錯不會報錯，只會靜默降級成另一個搜尋** —— `rg -r` 是 `--replace`，
   `-rn`/`-ril` 把後續字母吃成 replacement 值並停用 `-i`/`-l`/`-n`。一天三次：一次把自己的 bug
   誤診成終端顯示層問題、一次配 `2>/dev/null` 製造假的「0 hits」、一次漏掉 `Slack.java`。
   同族：**`git grep` 的 `\|` alternation 靜默匹配不到任何東西 —— 用 `-e` 逐個 pattern**
   （2026-08-04 差點據此結論「transformer 沒有 kafka code」）。
   → search flag 分開寫；`2>/dev/null` 會把「工具用錯」偽裝成「查無資料」。
3. **repo 裡的部署設定不是 runtime 真相，兩個方向都會騙你** —— 同一天違反三次：
   `MY_POD_NAME` 不在任何 manifest 但 prod 5370/5372 筆有值（差點據此開錯票、還為了消 guard
   警告移除欄位寫入）；`SENTRY_DSN` 佔位符在但 SDK 從未安裝；`deployment.yaml` 宣告 `secretRef`
   但那個 secret **根本不存在**（還照著叫別人去填）。→ prod 一個 `COUNT` 就能推翻三段推理。
4. **修改看起來會生效，實際那個值不離開服務** —— 修「資料沒傳到下游」的 bug 之前，
   **先打開送出去的 DTO/payload 型別確認欄位存在**，再去追它為什麼是空的。
   VP-17591 直到 merge + deploy + live 驗證通過**之後**才發現 `PlaceOrderRequest` 沒有
   address 欄位。**沿路每個訊號都是綠的，因為那些訊號測的是「我改的東西有沒有正確運作」，
   不是「我改的東西是不是問題所在」。**

5. **「排程 job 死了」是從輸出缺席推論出來的，而 job 其實每晚都在跑** ——
   dream log 連續三晚（08-01/08-04 及本晚初判）寫 daily digest「dead / still silent」，
   證據只有「`long-term-memory/daily-digest/` 最新還是 07-29」。今晚多查一層才發現：
   launchd 的 `StandardOutPath`（`~/.lis-daily-digest/main/logs/daily-digest/launchd.out.log`）
   是 **0 bytes、mtime 停在 6/23，從頭到尾沒被寫過** —— 我一度據此寫下「這個 job 從未執行」。
   但 script 自己另有 per-run log（`logs/daily-digest/YYYY-MM-DD_HHMMSS.log`），裡面
   **07-30 到 08-05 每天都有紀錄**，每次都跑到 `claude attempt 1/2` 然後
   `API Error: Connection closed mid-response` → `final rc=1`。
   → **宣告排程 job 故障前，先找 job 自己的 log，別只看 launchd 的 stdout/stderr**
   （很多 script 自己 redirect，launchd 那份會永遠是空的，而「空」看起來就像「沒跑」）。
   → 同時修正判斷：這不是三個 job 各自的 config bug，而是**同一個平台層 API 不穩**
   打到全部三個 automation（見本晚 dream log 的 Automation health）。

（1/2/3 已進 factory `ENGINEERING-LESSONS.md` #17/#18/#19，2026-08-04 merge；4 為候選未定案；
5 於 2026-08-05 加入 —— 這個 family 首次是**在 dream 自己的診斷裡**被踩到，而非在 ticket 工作中。）

### 找「既有機制」時先列實作形態的同義詞，並考古前一代（VP-17544 最貴的一次繞路）

搜 slack/webhook/alert/pagerduty 全空 → 寫完整個 Slack notifier 才被 Leo 一句
「我以前確實有 sentry message 傳到 C08C59A6TMF」推翻。漏搜的兩層根因：
- **關鍵字集合不足** —— 沒把 error-tracking 當成告警管道。（同型：beta program 的管理 API 叫
  `FeatureAccess`，不叫 beta。）
- **搜錯 source** —— 只搜 `lis-backend-emr-v2/src/proto`，那是 **subset 副本**
  （實測 `Object.keys(service)` 確認零個 `Feature*` RPC）。
  → **consumer repo 的 proto 副本不能用來回答「這個 service 有什麼 RPC」。**

→ Step 2 探索時就問「**這個能力在前一代服務是怎麼做的**」，並把 `SENTRY_DSN` /
`ALERT_WEBHOOK_URL` 這類佔位符當成**考古線索**往下追，而不是記成「閒置設定」。
補「缺失」能力前先考古；「要新增」與「做不到」是兩件事，寫成 finding 時要區分
（把前者寫成後者，讀者會理解成不可行）。

### 驗證判準的錯誤方向系統性偏向「通過」（VP-17591, 2026-08-04）

live-verify 的 SQL 把 UTC 22:30 誤寫成 15:30，撈到一整天的舊成功 row；只因為另一個 bug
（`finished=true` vs Prisma raw 的 `finished=1`）才沒誤報。那是運氣不是設計。
- 改用 **`id > baseline`**（單調遞增、無時區語意）取代時間窗。
- **最便宜的自檢：「如果現在什麼都沒發生，這個判準會不會通過？」**
- rolling deploy 的完成判準要綁「**新 pod 的身份 + 就緒**」，不能用
  `deployment.status.readyReplicas`（rolling update 期間計入舊 pod）—— 這正是 factory lesson
  第 12 條，寫完還踩。
- **on-prem pod 是否已更新，只能靠 DB 的 `hl7_file_input.last_update_pod_name`**
  —— 那個 cluster 不在本機 kubeconfig。兩次 deploy 都靠新 hash 出現在真實訂單上證明
  （VP-17544 `546b6869b8`、VP-17591 `777c956c9b`；AKS 側當時是 `844b49cc7f`）。

### 沒送訊息的 live 連線 preflight（VP-17593，可複用）

Leo 問「有實際測過嗎」時，在**不觸發真實副作用**的前提下閉合驗證缺口：
`kubectl exec` 進 running pod → 確認 env 真的注入（url/topic/connstr 長度）→ 從 pod 內用
kafkajs 做 SASL admin `connect` + `fetchTopicMetadata` → 證明 AUTH + REACH + topic 存在。
（fetch 後的 ECONNRESET 是 Event Hub idle-close 雜訊，不是失敗。）
**claim 要 live-config / live-call 證據，不能只靠 schema parity 推理。**

### 共用 repo 上有並行 agent/job — commit 前確認當前 branch（2026-08-04 實踩）

commit 一度落到背景 job checkout 的 `bugfix/leo/triage-prompt-step3-prefix-lookup` 上，
而 `git push origin main` 推的是不含它的舊 main —— **卻印出 "STM pushed"，因為 `| tail`
吃掉了 exit code**。管線末端的 `| tail` / `| head` 會吞掉前一段的失敗。

### blocked 判定有保存期限（VP-17537, 2026-08-03 Leo 流程糾正）

回報「這張票 blocked」前必須**重測 blocker**。VP-17537 的 blocked 理由（charging ACH 失敗）
早在 4 天前就被 sibling ticket VP-17538 的 payment-method walk 解掉，但答案照抄 7/29 的 STM verdict。
Leo：「實際上是你沒有去看其他的相關 ticket issue，對大方向不了解」。四部修正（均已 PR）：
1. `blocked` status 必須帶**可執行的** `unblock_when:`（寫成一個測試，不是一句敘述）；
2. 手工維護的 `relations:`（`unblocked_by` / `blocks` / `sibling`）與自動 `links:` 分離
   —— 55 條沒有型別的 flat `links:` 不會給你「該去讀哪張」的理由；
3. dream Phase 0.5 dependency propagation（shipped ticket → 在 dependents 上插 RE-CHECK marker）；
4. status 類問題的檢索要 sweep `relations:` 中 `updated:` 更新的票。
⚠ YAML 註解在 STM frontmatter 撐不過 `memory_scoring.py` 的 PyYAML round-trip —— schema 說明
只能放 factory template。

### 便宜的 payload 證明：response echo 一個只有我方持有的值（VP-17537）

要證明「我送出的 payload 真的含某欄位」而看不到 wire：charging 在 place-order 前就 mint 了
`julien_barcode 2608036004`，而 place-order 的 **response 回顯了它**；order-management 從不呼叫
charging → 這個值只可能來自我們的 payload。**找一個下游不可能自己知道的值，看它有沒有回聲。**

### 提出「需要新機制」前，先確認既有機制是否已覆蓋未來的案例（VP-17598, Leo 判斷勝出）

我把一個**歷史清理**需求包裝成**架構缺口**（「event-time 告警無法發現已卡住的 backlog，
所以需要週期性 sweep」）。但既有的 VP-17533 已把所有 throw 收攏進 `markFailure`，
未來每筆 retry 耗盡都會即時告警、不會再累積 → 剩下的 90 筆只是考古。
→ 區分「**過去的殘骸**」與「**未來還會再發生**」；只有後者才是機制缺口。

### Scope discipline：修自己的，其餘交出去，即使修起來很容易（2026-08-04）

VP-17594（setting module）已寫好 PR #552，Leo 判定非我方 scope 並直接關閉（「不需要管」）。
與 [[feedback_defect_found_must_be_ticketed]] 的 OTHER-team 分支同一條：交診斷、不自己開票、
不順手修。VP-17591 的 billing 元兇同樣處理。

### Cross-ticket review 2026-08-04（marker 2026-07-31 後 7 張 completed：VP-17537, VP-17412, VP-17544, VP-17587, VP-17591, VP-17593, VP-17595 + VEJO-DELETION-20260804）

三個橫跨這批的系統性樣態：
1. **同一 root shape 在一天內重複四次**（見上方「家族蒸餾」）—— 個別 lesson 各自記錄過但沒被
   當成 family，所以沒有一條救得了下一條。**把同形失誤合併成一條有名字的 family，比多記三條
   獨立 lesson 有用。**
2. **既有機制被「遷移遺失」而非「從未存在」**是這批的重複主題：Sentry 上報（emr-v2 遷移掉）、
   setting.service 的 Azure leg（env 從未 provision）、result consumer 的 on-prem fallback
   （退役後變成遮蔽 cloud 失敗的死路）。→ 面對「這個能力不存在」的結論，先假設它**曾經存在**。
3. **Leo 的判斷在這批贏了三次**（沿用 Sentry project 49、90 筆歷史略過、VP-17594 交出去），
   共同形狀都是**我把「乾淨的解法」排在「立刻能通的解法」前面**，或把別人的 scope 攬進來。

## 【家族延伸 2026-08-06】fallback 只要語意上是「猜」，就必須 fail loud（VP-17631 / VP-17524 / VP-17503）

同一晚三張票蒸餾出同一條，接續 patterns #5/#6/#9 與 2026-08-04 的「家族蒸餾」：
- **VP-17631**：order-package API 失敗時靜默退回 legacy first-match grouping。first-match 對
  superset package 天生會贏（10001 是第一個 key），所以 degradation 產出的是**合法但臨床錯誤**
  的文件 —— 沒有任何 error row，DB 全綠。
- **VP-17503**：report PDF 下載失敗時回傳寫死的 placeholder base64，record 標 GENERATED/TRANSMITTED。
  改成一律 throw → `GENERATION_ERROR` + BullMQ retry（沿用 VP-17342 既有機制，零 schema 變更）。
- **VP-17524**：反面教材證明這條是對的 —— `default:` 分支的 ERROR log 是這個 bug **唯一**被看見的
  原因。所以修 mapper 時刻意保留 `default:` fail-closed，只把「已知會出現的 modifier 前綴」結構化剝除。

判準：**degradation 的輸出如果自己也是合法文件，就不能靜默。** 能靠既有 retry 機制自癒的，
一律 throw；真正無法歸類的，fail closed 並保留 loud log 當 tripwire。

### 但 fail loud 之後要確認「有人在看」（VP-17631 查證後的缺口）
把靜默錯誤換成明確失敗，只走了一半。emr-v2 的實際處理鏈：
`ensureResultTransmissionRecord` 在 `generateHl7Content` **之前**（main :205 vs :217），
所以 throw 一定留 DB 痕跡（`GENERATION_ERROR` + error_message + `retry_count++` + `next_retry_at`）；
BullMQ `attempts:5`、exponential backoff base 120s（≈2/4/8/16 分，總窗約 30 分）；
用盡後 `onFailed` → `markPermanentFailure` → `next_retry_at = null`。
**缺口**：`TIMEOUT_RETRY`（VP-17343）只在請求層 timeout 觸發，**沒有掃 `next_retry_at` 的 cron**；
emr-v2 的 @Cron 只有 order fetch / mapping cache / scheduled reports，agent 端 DailyJob 也只看
order 側（hl7_fail）。→ 超過 30 分的上游中斷 = 報告不會送出、**且沒有人在看**那些 ERROR row。
改 fail-loud 的同時要問：這個 loud 誰在聽？

### 描述症狀要從 artifact 講，不要從變數講（VP-17524，我自己寫的票自己踩）
票是 2026-07-28 dream scan 我自己開的，症狀寫「OBX-8 abnormal flag TNP」—— 只讀到 mapper 就下筆。
再往下一層讀 encoder 才發現 OBX-8 是**被清空**、另外多一段 `NTE|1||Test Not Processed`。
同樣嚴重度、不同 artifact，而 NTE 才是人看到的那個。
**凡是會離開 process 的東西（HL7、API response、email、檔案），先追到邊界再寫症狀。**

### 別人家的 code 是比人更快更可靠的 oracle（VP-17524）
票自己的提案是「先跟 lab/report team 確認這個 type 的語意」。實際上三個獨立 repo
（producer + 兩個 consumer）已經把約定寫在 code 裡，一輪就把「要去問人」的票變成「已決定」的票。
向外求證前先問：**這個語意有沒有已經被誰實作過？**

### 離線重放 legacy 演算法 = 便宜的 root-cause 證明（VP-17631 / VP-17524 同形）
- VP-17631：用兩支 mapping API 的資料在本地重跑舊的 first-match 算法，精確重現當時檔案的
  OBX 分佈（74/1/5/2），**不需要當時的 pod log**。
- VP-17524：在腦中執行 Java 的 `parseResult2SampleTestStatus(">90")`，得到 legacy 會送 `N`。
凡是 port 自舊實作的服務，舊實作就是一份**可執行的 spec**；重放它比找歷史 log 便宜得多。

### read-only 「generate content」endpoint 是投遞管線最值錢的東西（VP-17524 工具面）
沒有 VPN、沒有部署、零副作用就能做出真 prod 資料的 before/after E2E：
1. `kubectl port-forward` prod configmap 指的那幾個 gRPC upstream 到 localhost；
2. 由**同一份 configmap** 產 `.env.local`，把 GRPC host 改寫成 127.0.0.1；
3. 讓本機 boot 變惰性：`POD_ROLE=web`（intake providers / pusher queue processor 都不註冊）
   ＋ `ENABLE_KAFKA_CONSUMER=false`（log 要確認 `KafkaReportFinishedListenerService` disabled）
   —— 才不會搶 prod 的 result-finished event；
4. `POST /api/v1/result/generate-content/:sampleId`（`send_result:false`）只做 gRPC get +
   `findFirst`；事後確認 `HL7_LOCAL_ROOT` 下零檔案；
5. admin JWT 用 configmap 自己的 `JWT_SECRET` HS256 本地簽（`internal_user_role:'admin'`）。
   ⚠ staging 的 `JWT_SECRET` 在 `lis-emr-v2-config`（不是 `-config-prod`），prod token 在 staging 會 401。
**control sample 才是讓 diff 變成證據的東西** ——「我想改的地方變了」很容易，
「其他都 byte-identical」才是要證明的那句。
（VP-17631 補充：`send_result=false` 的 dry-run **在 #333 merge 前不是零副作用** ——
它會沿用既有 record 並覆寫 `generated_hl7_content`/`file_size_bytes`/`updated_at`，
對已投遞的 record 做 dry-run 會讓 DB 與當時真正送出的檔案不一致。）

### staging 驗不到不等於沒驗（VP-17524）
staging 與 prod 共用 gRPC upstream 但指自己的 DB（192.168.60.11），而
`validateEmrIntegration`（step 2）跑在 mapper（step 3）**之前** —— prod 樣本在 staging 會先死在
"No result-enabled integration found"，永遠碰不到要測的 code。
這種情況 staging 只能確認「跑著正確的 commit」，功能證據必須來自 prod read-only 探針。
報告時要把這句寫清楚，不要讓「staging 驗過」含糊帶過。

### emr-v2 fresh worktree：一律 `npm test`，不要 `npx jest`（VP-17524 差點誤報）
`pretest` hook（`prisma generate --schema=prisma/schema.test.prisma`）才會建
`.prisma/test-client`。乾淨 worktree 上直接 `npx jest` 會紅 5 個 suite，**長得跟 regression 一模一樣**。
（接 repos.md 既有的 jest gotcha 清單。）

### zsh：`grep -r --include` 的 pattern 一定要引號（VP-17524）
`grep -r --include=*.java` 未加引號時 zsh 直接以 `no matches found` **中止整條命令**，
讀起來就像「legacy repo 裡沒有這段 code」。與 [[feedback_rg_dash_r_is_replace_not_recursive]] 同族：
**空結果先懷疑 shell/flag，再懷疑 codebase。**

## 【蒸餾 2026-08-06】兩個 stakeholder 在裁決「同一個 fallback」時，先確認他們講的是不是同一種 actor（VP-17628）

三輪才收斂的設計，形狀值得記住：
1. 我的 Step-4 提案：省略 provider → 查 clinic defaultProvider → 再退回 token customer（portal parity）。Leo 先批准了 token-customer fallback。
2. PM（Chris Wu）推翻：default 未設 → **ERROR，不准退回 token**；明給 provider 一律覆寫。
3. Leo 接著反對我「把三種 token 壓成一條 chain」的摘要：**customer-scoped token 本來就該以自己下單，根本不該去查 clinic default。**

最終不是一條 chain，而是**以 token type 為 key 的矩陣**：
customer token → self；clinic-only token → default-or-error；scope-less → 必須自帶 provider。
PM 的規則只適用 clinic-token 那一列。

**看似矛盾的兩個裁決，其實是在講不同的 actor class。** 我把它們攤平成一條規則才製造出衝突；
換成矩陣就同時滿足兩人，而且順帶消掉 skeptic 提的 namespace 漏洞（VP-17499 第二個 resolution point）
——不需要額外的 code。
→ 收到第二個 stakeholder 的裁決時，先問：**他跟前一個人講的是同一個主體嗎？**
別急著回報「兩位的意見衝突」。

### 「有 row」不等於「值可用」——設計 fallback 前先量化 unset 的分佈（VP-17628）
clinic_setting 的 `defaultProvider`，用 ClickHouse replica 掃 **52,615 個 active clinic**：
**37% 有可用值 / 37% 是 empty-string 的 row / 26% 根本沒有 row**。
empty-string 型跟可用型一樣多 —— 如果照直覺寫「row 存在就當有設定」，**19,000 個 clinic 會判錯**。
Live RPC 探針也確認了：clinic 153884 回傳 `value='' active=true`。
→ 任何 optional setting，「沒設定」至少有三種型態（無 row / 空值 / 明確 null），
**開工前先跑一次分佈統計**，這是幾分鐘的查詢換掉一個結構性 bug。
（同族：RPC 失敗 vs 設定未設，也絕不能混為一談——skeptic 抓到的第四點。）

### 移除 fallback 時，若 option flag 已無反向 caller，就整個刪掉而不是翻預設值（VP-17503）
whole-order 也改成 throw 之後，`throwOnFailure` 沒有任何 `false` 的 caller 了 →
直接把這個 option 拿掉，而不是把預設值翻成 true。改動因此變成幾乎純刪除（-98/+32），
沒有留下「還可以關掉」的暗門。**參數的存在本身就是承諾它會被用到兩種值。**

### 「for discussion」型 ticket：把 Step 3/4 壓成一個帶推薦的 AskUserQuestion（VP-17503）
當兩個選項的差別是**產品語意**而不是技術風險，debate subagent 沒有加值。
VP-17503 是「騎在已驗證機制上的刪除型改動」，一個帶明確推薦的提問，Leo 幾秒就回。
→ 判準：**選項差在技術後果 → debate；差在產品語意 → 直接問人。**

### 出貨 client 之前，先用 repo 自己的 proto 對 prod 打一次唯讀 RPC（VP-17628）
在寫 GetClinicSetting client 之前先實際呼叫 prod，一次確認了 proto 欄位命名（`keepCase`、`isActive`）
以及 configured / unset 兩種回傳形狀。比讀 proto 檔推測便宜太多，
而且這正是上面那條「37% 是 empty string」被發現的方式。

### worktree + config-yaml-coupling pre-commit hook：yaml 快照只在 main checkout（VP-17628 / VP-17589 兩次踩）
`lis-emr-v2-config.yaml` / `lis-emr-v2-config.prod.yaml` 是**未被 track 的檔案，只存在於主 checkout**。
新開的 worktree 裡沒有它們 → hook 對任何碰 `GRPC_V2_SETTING_*` 之類 env 的 commit 直接擋下。
解法是把那兩個 yaml **複製進 worktree** 讓 hook 解析得到（不是 `--no-verify` 繞過）。

## 【蒸餾 2026-08-10】CI 變慢的真正原因不在 Jenkinsfile 裡 —— 先跟 CI server 要每個 stage 的實測時間（VP-17653 / VP-17656）

emr-v2 build ~20 分鐘。讀 Jenkinsfile 推理出三個嫌疑（sequential rollout waits、
dead prepare stage、沒有 .dockerignore），修完只降到 10.4 分。**最大的那一個讀檔案永遠看不到**：
staging build 收尾的 `docker image prune -f` **沒有 filter**，把 multi-stage build 的
untagged 中間層全刪了 → 每一次 build 兩個 `npm ci` 都重跑。
證據是去 Jenkins API 拉 console log 比對 cache 標記才浮出來的：tagged runtime layer 顯示 CACHED，
untagged 的 dep/builder layer 全部 RUN。改成 `--filter "until=72h"` 之後
main #255 的 Docker Build 從 **292s → 5.4s**（29/32 cached）。

可攜的紀律：
- **優化 pipeline 前，先從 CI server 自己的 API 抓每個 build 的 stage 耗時序列**
  （這裡是 http://192.168.60.9:9602，multibranch job LIS-EMR-V2-BACKEND；
  掃 8080 找到的那幾台 X-Jenkins 是別隊的實例，帳密只在 60.9:9602 有效；
  POST 要先跟 `/crumbIssuer/api/json` 拿 crumb 並帶上 cookie；query 含 `[]` 要用 `curl -sg`）。
- **一次 build 變長不等於 regression**：main #256 的 14 分鐘是因為 #341 動了 package.json →
  npm ci 層合法失效（一次性）。判 regression 前先看**哪些層失效、為什麼**。
- **`prune` 這類「清理」指令是 cache 的天敵**，而它造成的傷害只會表現為「build 有點慢」，
  不會有任何錯誤訊息。任何無 filter 的 prune/clean 都該被視為每次 build 付一次全額成本。

### `parallel` 讓「驗證了一邊」不再等於「兩邊都好」（VP-17653）
把 on-prem 與 AKS 的 rollout 併成 `parallel` 之後，我在 AKS 側看到新 pod、正確 image、log 乾淨，
但這**不能證明 on-prem 那一支過了**。在 parallel 結構下唯一的聯合訊號是 **build 整體 SUCCESS**
（任一支失敗會讓整個 build 失敗）。要單獨確認某一支，就得直接查那個 cluster 的 image SHA。
→ 併行化會改變「什麼證據證明什麼」，改完 pipeline 要同步更新自己的驗證判準。

### 慢，往往是另一個 bug 的症狀（VP-17653 → 抓到跨環境覆蓋）
追 main build 為什麼 14 分鐘，才發現 main 每次都會 apply
`azure-lis-emr-v2-deployment.yaml`（**on-prem STAGING** 的 deployment），而它 pin 的是
`lis-backend-emr-v2:latest` = **prod image**。自 VP-16463 起，每次 main build 都把 on-prem staging
的 SHA 蓋成 prod code，並附帶觸發一次完整 staging rollout（等 ≤300s）與 concurrent build 競態。
**沒人回報過**，因為結果不是錯誤而是「staging 跑著別的版本」。
→ 效能調查會強迫你逐行讀 deploy 腳本，是發現這類靜默錯誤的少數場合之一。

### 被註解掉的 stage 是一顆倒數計時的刪除彈（VP-17656）
emr-v2 的 `stage("test")` 2025-09-17 因為別的問題被註解掉，2025-12-08 一次「remove commented code」
就徹底消失。之後 **8 個月零 lint、零 unit test、零 typecheck**，而 repo 裡躺著 82 個 `*.test.ts`
和完整的 jest scripts。恢復時的現況盤點也值得記：unit suite 其實**健康**
（101 suites / 1168 tests / ~14s / SQLite test DB / 無外部相依），壞掉的是 lint
（裝了 eslint 9 但**根本沒有 config 檔**）。
→ (a) 註解掉 CI stage 等於刪除，要嘛修好要嘛開票；
  (b) 接手一個「沒有測試」的 repo，先跑一次再下結論——常常測試是好的，只是沒人叫它跑；
  (c) Jenkins multibranch 的 `WildcardSCMHeadFilterTrait` 若是 `main staging`，
      feature branch **根本不會 build**，PR 完全無 gate——「CI 沒跑」有時是 branch filter 的事，不是 stage 的事。

## 【蒸餾 2026-08-10】查不到錯誤，先確認你的查詢查得到錯誤（VP-17651）

P1「Error Downloading Reports」。pod log 48 小時 3,866 筆 /pdf **全部 200**、ingress 零 4xx/5xx、
Datadog `status:error` **零筆**。三個獨立來源都說「沒有錯誤」。實際上那週有 **236 次 500**，
ticket 當天尖峰失敗率約 10%。三個「沒有」各有各的假象：
- **pod log 只涵蓋 pod 的壽命**。全 cluster 的 node 在 2026-08-08 維護時換過，所有 pod 都只有 42-43h 大，
  事故當天（08-07）的 log **在本地已經不存在**。「查了 48 小時」聽起來很久，但它從事故之後才開始。
- **Datadog 的 `status` 不是服務的 severity**。report-pdf-engine 的 pino level-50 因為沒有 pipeline remap，
  全部落成 **`status:info`** → `status:error` 對這個 service 永遠回零。正確查法是
  `@err.type:*` 或 `@res.statusCode:500`。
- **ingress 也可能看不到**：被瀏覽器 CORS 擋掉的請求，server 只留下一筆乾淨的 OPTIONS 204。

→ 紀律：**把「零筆」當成證據之前，先用一個你已知存在的正例校準這個查詢**
（換個過濾條件、換個時間窗、或直接查一筆你確定發生過的事件）。
校準不過的查詢，它的零沒有任何資訊量。同族：[[feedback_never_conclude_breakage_from_a_quiet_window]]（那條是輸入端為空），
這條是**儀器本身對準了錯的欄位**——兩者的「零」長得一模一樣。

### 「明顯的 hardening」可能會放大故障（VP-17651，假設被證據推翻）
初期假設是 Puppeteer browser pool 卡死，而 `/health` 不碰 pool → K8s 看不見。
提出的修法是 pool-aware readiness probe。**Datadog 時序推翻了它**：失敗在 08-07 16:30Z 之後歸零，
pool 自己恢復了，這是純容量問題（5 pods × 2 browsers = 10 併發，render 佔用 2-33s，acquire timeout 只有 10s）。
若真的上了 pool-aware readiness，**尖峰時會把最忙的 pod 踢出 rotation，讓爆量更嚴重**。
→ 對「還沒被證實的故障模式」做的加固，要先問它在**相反的故障模式**下會怎樣。

### 提高併發度的同時沒有提高資源上限 = 之後才炸的 OOM（VP-17651，2026-08-10 當晚兌現）
容量修法是 acquire timeout 10s→30s（改成排隊而不是 500，因為 ingress 讀取逾時 60s 有 headroom）
+ replicas 5→8。我刻意**沒有**動 `BROWSERS_PER_WORKER`，理由寫在 STM：memory limit 曾為了 2 個 browser
從 2Gi 調到 4Gi。後來 report team 自行把它設成 3，**memory limit 仍是 4Gi**。
當晚 01:18Z 就有一個 pod `OOMKilled`（exitCode 137）。
→ **每個 instance 的併發度與它的資源上限是同一個決定**；只動其中一個，另一個會在流量尖峰時替你做決定。
本例的具體帳：limit 4Gi 是照 2 browsers 算的，現在 3 browsers。

### 修完之後同一個人回報同樣的症狀 ≠ 沒修好（VP-17651 / VP-17659，2026-08-11）

pool exhaustion 修掉、容量從 10 併發拉到 24、Datadog 自 08-07 16:30Z 起零筆 500。
隔天同一位客戶連續回報兩次「還是不行」，看起來像「你根本沒修好」。實際上是**第二種故障類別**
打在同一個使用者身上。分辨它靠三個互相獨立的訊號，任何一個單獨都不夠：

1. **錯誤字串本身就是分類器**。axios 的 `Network Error` = 根本沒收到 HTTP response；
   真的 500 會顯示 `Request failed with status code 500`。使用者截圖裡的那行字要當證據讀，不要當抱怨讀。
2. **她的 accession 在 server 端有沒有留下痕跡**。針對該 accession 查 ingress + engine：
   全部 200、零 5xx、零 499 → 那次失敗**從來沒有到達我們的 edge**。
   （反例校準見上一節：查不到錯誤前先確認查詢查得到錯誤。）
3. **ingress 的 499 有沒有固定秒數**。同一 sample 的 retry pair 兩次都在 **~19.8s** 被切斷
   = 中間某個 proxy/VPN 的固定 timeout 簽名；axios 那邊沒有設 timeout，人手動取消也不會這麼準。
   499 秒數散亂才是使用者自己關頁面。

**定位到「哪一段網路」的技巧**：比對同一個頁面上**成功**與**失敗**的請求各自打到哪個 domain。
本例 viewer 的資料走 `api.vibrant-wellness.com`（她可以）、下載走 `api.vibrant-america.com`（她不行、
且我們完全沒有 log）→ 不是「網路慢」而是 **domain-specific 的阻斷**（她公司防火牆/DNS filter/SSL inspection，
或 Cloudflare WAF 把她擋掉 —— CF 的 block page 沒有 ACAO header，瀏覽器就報成 `Network Error`，
而且被 CF 擋掉的請求**不會進 origin log**，跟「純 client-side」長得一樣）。

**要給使用者的東西是一個 discriminator，不是一句「再試一次」**：請她在瀏覽器直接開失敗那個 domain 上
一個**公開、無需 auth、回應極小**的 URL（本例 `/v1/report-pdf-engine/health` → `{"status":"ok"}`）。
開得起來 → 問題在那個特定請求（查 CF Security Events）；開不起來 → 她的 IT 要放行該 domain，
且瀏覽器的錯誤碼會直接告訴你被擋在哪一層。一次來回就把「我們 vs 她的網路」切乾淨，
不必再收第四支 Loom。

→ 紀律：**「同樣的症狀」不是同一個 bug 的證據**。修完之後的回報要重新走一次分類，
先問「這次的失敗在我們這邊留下什麼痕跡」——沒有痕跡的失敗和有痕跡的失敗是兩張不同的票。
同族：[[project_result_push_has_no_idempotency_gate]] 那種「row 看起來乾淨」的假象，
以及上一節的查詢校準。

## 【家族延伸 2026-08-12】mock 掉的 collaborator 沒辦法驗證「你叫它的那個名字存在」（VP-17685）

VP-17685 把 julien barcode 從 coresamples v2 換去 v1。第一次 ship（PR #343 + promotion #344）
上線後，staging 立刻噴：

```
generateBarcodeForSampleID failed for sample 2554096-2554098:
  client.generateBarcodeForSampleID is not a function
```

gRPC client 物件上的 method 是用 **proto 名字**掛的；code 用的 camelCase 別名把結尾的縮寫
吃掉了（`...ForSampleID` → `...ForSampleId`），於是那個 property 是 `undefined`，call 直接 throw。
PR #348 只改名字就修好。

**三道綠燈全部沒擋住，而且是同一個原因**：
- `npx jest src/modules/grpc src/modules/hl7-order-processing` → 31 suites / **375 passed**
- `npx tsc --noEmit` → 0 errors、`nest build` clean
- VP-17656 剛修好的 CI gate 也跑了也綠了

因為 spec 裡那個 client 是 **mock**。mock 對你發明的任何名字都會乖乖回答，所以 spec 用錯的名字
去 assert 用錯的名字，自己跟自己一致。`tsc` 也擋不住 —— 動態產生的 gRPC client 型別上那個
method 名字本來就不在編譯期存在（`any` / index signature / `keepCase` 產物）。

→ **判準**：unit test 綠燈證明的是「呼叫方的邏輯自洽」，不是「被呼叫方接得住」。凡是
**跨 process 邊界、名字在編譯期不存在**的呼叫（gRPC/proto 產生的 client、`grpcurl` 的
service.method、dynamic dispatch、字串 key 的 event/topic 名），mock 的斷言價值趨近於零，
必須有**一次真的呼叫**才算驗過 —— 一次 live call、或退一步用 `grpcurl` 打同一個 method 名。
同族既有變體見 line 1145（測試 mock 掉相依路徑 → 假信心）與 line 652（mock-seam 盲區：
fixture 設了 live pipeline 從不設的欄位）。這次是**第三種**：mock 掉的是**名字本身**。

配套的錯誤字串辨識（跟 line 1089 的 grpcurl 三種錯誤並列）：
- `client.X is not a function` → **本地** client 物件上沒這個 property，名字拼錯 / 大小寫 /
  縮寫尾巴被 camelCase 轉換吃掉。**還沒送出任何 request**。
- `Code: Unimplemented` (12) → 送出去了，server 沒註冊。
兩者差一個 network hop，但看起來都像「RPC 壞了」。

→ 紀律延伸（同 family，line 1342）：這次「沒驗證它真的在做我以為的事」的那個環節，
是**測試自己**。綠燈的來源如果是自己寫的替身，它證明的只有替身的行為。

## 【家族延伸 2026-08-14】非致命的 catch 會把「100% 失敗」轉成「零訊號」（VP-17685 lesson 3）

同一張 ticket 的第三條教訓，和上面那條（mock 掉名字）是同一次事故的另一面。
`generateBarcodeForSampleID` 這支 RPC **失敗了大約 18 個月**，代價只有一行 warn。
沒人看，因為 barcode 是 best-effort、失敗不影響下單。它之所以在 2026-08 浮出來，
純粹是 staging 的 charging 壞掉、逼得每一單都走 no-charge path 才撞上。

→ **判準**：`catch { logWarn(...) }` 把「這個功能從來沒有成功過」和「這個功能一切正常」
壓成同一種可觀測狀態（都是安靜的）。凡是包在非致命 catch 裡的外部呼叫，
**成功路徑也必須留下訊號**（成功 log / metric / 一個會被寫進 DB 的欄位），
否則你永遠只能證明它有沒有大聲壞掉，不能證明它有沒有在運作。
- 反向操作（診斷用）：要判斷一段非致命邏輯是死是活，**先確認你的查詢查得到「成功」長什麼樣**。
  查不到失敗 ≠ 健康（同 line 1637 VP-17651）；查不到**任何**紀錄 = 這條路徑對你完全不可觀測，
  此時唯一的答案是「不知道」，不是「正常」。VP-17685 部署後正是這個狀態。
- 連帶：`fail-loud vs fail-silent` 的決策（line 1470 家族）不只發生在**錯誤**路徑上，
  也發生在**可觀測性**上。一個永遠安靜的成功，和一個永遠安靜的失敗，長得一模一樣。

## 【journal 蒸餾 2026-08-14】要證明 prod 上實際跑的是哪條路：找只有那條路會寫的字串（VP-17714）

VP-17714 要回答「使用者說的『轉手』到底走哪個 code path、歷史上發生過幾次」。三種嘗試，
只有一種站得住：

1. **event pair 推論**（同 accession、一取消一新建）→ 撈到 4 組。這是**推論**，不是證據。
2. **`v2_event_accession_audit_log.reason = 'clinician switch reschedule, original event N'`**
   → 同樣 4 筆。這串字**只有 `rescheduleClinicalConsult` 會寫**，所以它同時證明了兩件事：
   數量是 4，**而且前端確實在打這個 mutation**（不是還停在舊的 `updateEventByPatient`）。
3. **`participant.created_at > event.create_time`**（想抓另一條 in-place 換人的路）→ **不可用**。
   `replaceEventParticipants` 是 deleteMany + createMany，每次帶 participants 的 update
   都重寫 `created_at`，抽樣 30 筆多數根本不是換人。

→ **判準三條**：
- **要指認執行路徑，找「指紋字串」**——只有那條路會寫進 DB/log 的常數（audit reason、
  scope key、特定的 error message）。它比任何用資料形狀反推的 heuristic 都硬，
  而且順便驗證了呼叫端真的在用新介面。
- **衍生訊號的可用性取決於寫入模式**：任何 delete-and-recreate 的實作都會重置
  `created_at`/`id` 序，用它們做時間推論就是雜訊。查之前先看那張表是怎麼被寫的。
- **另一條路沒有指紋 = 你無法量化它**。這時要回報的是「這條路存在、無法追溯」，
  不是估一個數字。VP-17714 的殘留路徑（`updateEvent` → `replaceEventParticipants`
  原地換人）就是這樣交回給 Leo 的，他一句「換人一律走 reschedule」把它變成非問題——
  **誠實說不知道，換來的是一個規則，比一個假數字有用**。

附帶兩條同 ticket 的實作紀律：
- **解不出來時清空 + warn，不要保留舊值**。保留舊的 meeting url = 保證把人導向錯誤的房間；
  清空只是缺資訊。**「錯的指標」比「沒有指標」傷害大**，前者無法察覺，後者可補。
- **外部 HTTP 解析放 `$transaction` 之前**。交易期間不能卡一個 outbound call。
- **repo 本來就有 pre-existing 失敗 suite 時，測試結論一律用 baseline 對照**（同 line 791
  的 tsc 手法，套到 jest）：base 17 fail / branch 16 fail，逐 suite diff 出唯一差異是
  已知 flaky 的 `auth.guard.spec.ts` → 才敢說「零新增失敗」。不做對照，「還有 16 個紅的」
  這句話沒有任何資訊量。

### 兩個小陷阱（VP-17715 實作時撞到，emr-v2）
- **worktree 的 node_modules 從舊 branch checkout 複製過來會少東西**（staging 新加的
  `@azure/identity`、`@sentry/node` → 5 個 TS2307）。複製完先 `npm install` 再相信 build。
- **`npx jest <完整路徑>` 在 emr-v2 會 match 0 tests**（testRegex 與路徑形式不合）——
  用名稱 pattern：`npx jest kafka-report-finished-listener`。

## 【蒸餾 2026-08-15】排程 job 寫出 "BLOCKED" 報告 = 那天沒有訊號，不是那天沒有問題

`DailyJob/hl7_fail` 與 `DailyJob/result_fail` 的 launchd job **連兩天（8/14、8/15）**在 pre-flight
就撞到 `lisportalprod2:3306` 不可達（VPN 隔夜自動斷線，腳本的 headless 重連被
`Connect capability is unavailable. Another Cisco Secure Client application acquired it.` 擋掉），
於是各寫了一份只有 `## BLOCKED — prod DB unreachable` 的報告就退出。

腳本本身做對了：它明講「**This is NOT a "no failures" result**」。真正的破口是**下游沒有人讀那句話**
—— 8/14 的 dream 照常跑完、digest 照常出，沒有人注意到當天的失敗監控其實沒跑。連續兩天盲區。

8/15 晚上 VPN 恢復後手動補跑，兩份都拿到真結果：
- HL7 triage：乾淨（72h 內 11 筆，`parse_finished=0 AND retry_num=0` 為 0 筆，且有連線 sanity check）。
- result_fail：**不乾淨** — undelivered 從 8/13 的 23 筆漲到 26 筆；`Cascades` 新增一筆
  8/13 13:46 的 `PERMANENT FAILURE`（累計 6 筆失敗，**last success 停在 2026-06-01**）。
  也就是說補跑真的撈到了新東西，盲區不是空的。

紀律（可直接套到任何有 pre-flight 的排程 job）：
1. **消費排程 job 產出前，先驗它那天真的跑完了** — 讀報告的第一段、比對檔案 mtime，
   不要看到「有檔案」就當作「有結果」。`BLOCKED` / `SKIPPED` 檔案要當成缺漏處理。
2. **連續兩天缺訊號要升級**，一天可能是巧合，兩天是系統性（這次正是兩天）。
3. **前提條件恢復後要補跑**，不要等下一次排程 — 排程只看當下，不會回填昨天的窗口。
4. 呼應 memory「empty result ≠ no failures」：這是同一條原則的**上游版本** ——
   連查詢都沒發出時，連「空結果」都不存在，只有一份看起來很正常的檔案。

## 【遷移 2026-08-16】原生 auto-memory 退役時保留的操作性事實

> 來源：`~/.claude/projects/{slug}/memory/` 的 `project_*` 條目。只搬「本檔還沒有」的，
> 已被本檔或 `emr-integration.md` 覆蓋的直接丟（archive 有原件）。

### Atlassian MCP 的 JQL search 上限是 5 筆，且無法分頁

`mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql` 不管 `maxResults` 設多少都只回 **5 筆**，
其餘記在 `remainingCount`，而且 `pageInfo.hasNextPage: false`、**沒有 `endCursor`** — 不能翻頁。
砍 `fields` 也不會提高上限（`summary`/`description` 沒要也會回）。

需要完整結果集（daily digest、「今天更新的所有 ticket」、逐票 transition）就直接打 Jira REST：

```bash
EMAIL=$(grep -m1 -oE '[A-Za-z._-]+@[A-Za-z.-]+' ~/src/credential/atlassian-api-token.md)
TOKEN=$(grep -m1 '^token:' ~/src/credential/atlassian-api-token.md | sed 's/^token:[[:space:]]*//')
curl -s -u "$EMAIL:$TOKEN" -G "https://vibrantamerica.atlassian.net/rest/api/3/search/jql" \
  --data-urlencode 'jql=project = VP AND updated >= "2026-08-12 00:00" AND updated < "2026-08-13 00:00"' \
  --data-urlencode 'maxResults=100' \
  --data-urlencode 'fields=key,summary,status,assignee,issuetype,created,updated,priority' \
  --data-urlencode 'expand=changelog'
```

`expand=changelog` 是關鍵：沒有它只看得到現況 status + `updated` timestamp，說不出「誰在什麼時候改了什麼」。
加 `fields=comment` 可在同一次呼叫拿到留言。

**為什麼不只是方便**：`updated` 這個數字本身會騙人。2026-08-12 的 50 張「已更新」VP ticket 裡，
有 17 張只是 `Automation for Jira` 在 09:00 寫 `Duration`/`Start date` — **34% 是自動化雜訊**。
只有 changelog 分得出來。憑證在 `~/src/credential/atlassian-api-token.md`（HTTP Basic）。

### macOS TCC 會讓 ~/Downloads 的檔案「看起來不見」

TCC 可以擋掉目錄列舉（`ls: Operation not permitted`、zsh glob "no matches"、find/mdfind 靜默漏），
但**仍允許直接存取已知完整路徑**（`stat` / `cp ~/Downloads/exact-name` 都會成功）。

2026-07-23 BioInsights SFTP 重測時，ls/find/mdfind 全都找不到 `bioinsights_key.ppk`，
於是結論「被移走或刪了」，又找了 20 分鐘 — `stat` 打原本記得的完整路徑，檔案一直都在。

**做法**：`~/Downloads`（或 Desktop/Documents）底下的檔案「消失」時，**先 stat 記憶中的完整路徑**，
再去別處找或下結論。shell 列不出來時 `osascript` 的 System Events 也列得到。

### Session transcript 是以「工作目錄路徑」為 key 的

Claude Code 把 session transcript 存在 `~/.claude/projects/<escaped-path>/`。
2026-07-06 本 repo 從 `/Users/hung.l/src/lis-code-agent` 改名成
`/Users/hung.l/src/vibrant-america-working-agent`，`claude --resume` 就看不到之前的 session 了
（「上個 session 東西不見了」）— 目錄改名會把 transcript 孤兒化在舊資料夾，實際沒有遺失。

154 個改名前的 session 已 rsync **複製**（非搬移）到新的 escaped-path 資料夾；
舊資料夾 `-Users-hung-l-src-lis-code-agent/` 保留不動，因為背景 job 可能還在往那裡寫。
若日後再改名：把 `*.jsonl` 與 session 子目錄複製到新路徑資料夾，合併前先 diff。

### project-agent-factory 有兩份 clone，舊的那份會拖垮 session context

Factory 活的 clone 在 **`~/src/project-agent-factory`**（remote `project-agent-factory.git`）。
`~/agent-core` 是 2026-07 改名前留下的殘骸，remote 還指著舊的 `agent-core.git`，
2026-08-16 落後 origin/main **93 個 commit**。

`~/.claude/CLAUDE.md` 原本 symlink 到 `~/agent-core/AGENTS.md`，所以每個 session 載入的
user-level context 都是舊的（缺核心原則 0、wave-doc 規則、以及點名本 instance 的 sync 指令）。
**檔案存在、也沒改名，只是活檔案躺在死掉的 clone 裡**，所以什麼都不會報錯。
2026-08-16 已把 symlink（含 `~/.claude/skills/` 兩條、`~/src/.claude/skills/` 兩條壞掉的）全部重指。

另一個相關陷阱：factory 常停在未 merge 的 `lesson/...` / `fix/...` branch 等 Leo review，
所以 `ENGINEERING-LESSONS.md` 可能有 `main` 沒有的條目，直接 `checkout main` 會像是被刪了。
本機 `main` 也會獨立於 `origin/main` 變舊 — 兩邊都要看。

### trans-v2 calendar 的問題先查 reference doc

`docs/reference/trans-v2-calendar.md`（本 repo）是 2026-07-28 寫的完整參考：17 個子模組、
7 個核心功能含 file:line 錨點、calendar_prod 表目錄 + prod row counts、GraphQL/REST 介面、
auth roles、Kafka topics（只有 producer；v2 沒有 BullMQ，Bull 在 legacy LIS-transformer）、
4 個 cron、以及 gotchas（150105 magic practice、只有 is_canceled 的狀態、dead tables）。
Calendar 問題先從這份回答，只需重驗行號與「現況」類主張。

### calendar audit log 的 actor id 怎麼還原成人

`v2_event_accession_audit_log.actor` / `v2_event_accession_claim.claimed_by` 是
`'user:' + getUserId(jwt)`（LIS-transformer-v2 `auth.guard.ts`）：clinic-user token → `user_id`，
patient token → `patient_id`。

那些數字是 **`lis_core_v7.user.user_id`** — 不是 `internal_user_id`（`internal_user` 表裡一個都沒有）、
不是 `customer_id`、也不是 `calendar_owner_id`（1147 筆 claimed row 裡 0 筆 actor == creator calendar owner）。

```bash
CH="http://192.168.62.85:8123/?user=portalclick&password=ebRiCiTypIRa"
curl -sS "$CH" -d "SELECT user_id, username, email_user_id FROM lis_core_v7_replica.user WHERE user_id IN (...) FORMAT TSVWithNames"
# 要名字：join lis_core_v7_replica.customer ON customer.user_id = user.user_id
```

用 `lis_core_v7_replica.*`，不要用 `lis_core_v7.*` — 非 replica 的 ClickHouse 快照停在 2024-10，
新帳號會靜默回零筆。

**陷阱：id 命名空間會撞。** `user_id=173014` 是 David Thayer（customer 47292），
而 `patient_id=173014` 是完全另一個人（PAUL POPKIN）。audit row 不記錄是哪種 payload 產生的，
所以指名道姓前要先確定 code path（clinic-user mutation 還是 patient mutation）。
發現於 VP-17577（重複 consult booking）triage。

### Beta program 的管理 API 叫 FeatureAccess，不叫 beta

Beta program 是全公司 practice 層級的 feature-flag 機制（`betaProgram` +
`beta_program_participations`，consumer 走 gRPC `CustomerService.FetchCustomerBetaProgramsForClinic`）。

**REST base URL**（LIS-backend-coreSamples，那個 Nest 的，**不是** Go 的 v2 service）：
prod `https://api.vibrant-wellness.com/v1/lis/lis-core-service/api/...`、
staging `.../lis-corestaging-service/api/...`。**`/api` 這段不能省**（`app.setGlobalPrefix("api")`），
省掉會拿到很誤導的 `404 {"message":"ENOENT: ... '/client/index.html'"}`。
不要跟 `/v2/lis/coresamples/...` 搞混，那是 Go 的 v2 service，這些路徑會回純文字 `404 page not found`。
Auth 是 HS256 JWT（同 emr-v2 上游呼叫用的 `JWT_SECRET_PROD`），**不加 `Bearer ` prefix**。

**gRPC 才是主要介面，而且名字裡沒有 beta** — VP-16490 "Feature Access Management"
在 `lis.CustomerService`（prod v1 `192.168.60.6:30276`，2026-08-03 驗證可用）：

| RPC | Request | 備註 |
| --- | --- | --- |
| `GetFeatureAccessWhitelist` | `beta_program_id`, `search_input` | 列出某 program 全部 entry，含 customer_name / clinic_name / added_by / added_date |
| `AddFeatureAccessRecord` | `beta_program_id`, `customer_id`, `clinic_id`, `internal_user_id` | **`customer_id` 有值 = provider 層級，`clinic_id` 有值 = practice 層級；不適用的那個填 0** |
| `RemoveFeatureAccessRecord` | `id`（participation record id）, `internal_user_id` | |
| `SearchProvidersAndPractices` | `search_input`, `limit` | admin picker |

**為什麼之前找不到**：搜的是 `beta` / `program` / `participation` / `enroll`，但 RPC 叫 **FeatureAccess**；
而且第一輪只搜了 emr-v2 的 `src/proto/customer.proto`，那是個 **subset copy**，這些 RPC 一個都沒有。
要用權威版 `LIS-backend-coreSamples/protos/customer.proto`（coreSamples 沒裝 deps 就借 emr-v2 的 node_modules 載）。

兩個花掉真實時間的坑：(1) participation 只吃數字 `beta_program_id`，不吃名字，而且
`addBetaProgramParticipation` 走 `findUniqueOrThrow` — program row 必須先存在；
(2) **沒有 create-program API**，全 codebase 零個 `prisma.betaProgram.create`，
新 program 仍要手動 insert DB。所以「讓 practice 加入」是自助的，「開一個新 flag」不是。
另外**不要拿 `FetchCustomerBetaProgramsForClinic` 判斷 program 存不存在** — 它只回某 clinic
有參加的 program，分不出「program 不存在」和「存在但零參與」（VP-17584 就踩了這個）。
已知 id：`express_checkout`=2、`gz_ny`=33（VP-17117 的 NY routing gate）；2026-08-03 共 39 個 program。

### api-product sandbox 測試 client 的憑證與 OCR 陷阱

api-sandbox（`api-sandbox.vibrant-america.com`）的測試 client 憑證與 token recipe 存在
`~/src/credential/api-product-sandbox-test-client.md`（client `api-product-test-client-3194`，
scope result/report；`POST /v1/oauth2/token` 帶 `algorithm=RS256`）。任何 api-sandbox 認證測試先讀那份。

2026-07-28 的 FHIR 503 triage 花了一小時重推怎麼拿 sandbox RS256 token 才寫下這條。
client registry 在 staging Auth0 postgres（192.168.60.11:5432，secret 已 hash —
用 ephemeral `kubectl run --image=postgres:16` pod 讀），secret 本身只走 out-of-band 發放。

**截圖貼過來的 client_id 會被 OCR 弄壞**（大寫 I 與小寫 l），要對 `Client` 表的
`clientId` / `secretLast4` 核對。另：2026-07-28 起所有 client_credentials 的 CUSTOMER token
過不了 FHIR session check（403，VP-17522 — session row 的 customer/clinic 是 NULL）。

## 【遷移 2026-08-16 第二批】workspace-keyed store 的操作性事實

> 來源 `~/.claude/projects/-Users-hung-l-src/memory/`。同批已覆蓋的（appserver04 SSH、
> coresamples v2 sample id、trans-v2 calendar service、cloud migration endpoints、
> VP-17065 daily report）不重寫；原件在 `archive/native-auto-memory-workspace-2026-08-16/`。

### 三道 git guard 現在走 factory 的 `core.hooksPath`（2026-08-16 搬家）

**現況**：`framework/githooks/{pre-commit,pre-push}`（factory，有版控、有 13 案 test），
以 **global** `git config --global core.hooksPath` 接線。全部可 `--no-verify` 略過。

- **guard 1 config coupled with code** — staged 新增的 `process.env.X`（字面形式；刻意不涵蓋
  解構與 `ConfigService.get`）若沒有同時出現在 repo 根目錄那對 ConfigMap（`*-config.yaml` +
  `*-config-prod.yaml`）的 `data:` 區 → 擋 commit。對應 INCIDENT-20260601（重犯 3 次）。
  **範圍靠形狀判定**：repo 有那對檔案就生效，沒有就跳過。
- **guard 2 no CJK in code** — staged 新增的 `.ts/.js/.sql` 行含 CJK（perl `-CSD`，因為 BSD
  grep 沒有 `-P`）→ 擋。markdown/docs 不查。全 repo 生效。
- **pre-push build gate** — `npx prisma generate` + `npm run build`，任一失敗擋 push。
  **明確 opt-in**（hook 內 `BUILD_GATE_REPOS`，目前只有 `lis-backend-emr-v2`），不是「有
  build script 就跑」——在沒講好的 repo 上每次 push 都 build 是沒人同意過的流程變更。

**兩個必須知道的性質**：

1. **會串接 repo 自己的 hook。** 設了 `core.hooksPath` 之後 git 會**完全忽略** `.git/hooks/`，
   而 git-lfs 正是把 pre-push/post-commit/post-merge/post-checkout 裝在那裡（EMR-Backend 就
   有這四個）——把它們靜音會弄壞 LFS pointer。所以 shared hook 先跑 repo 自己那份並尊重其
   exit code。解析那個路徑要用 `--git-dir`，**不能**用 `git rev-parse --git-path hooks`：後者
   在 hooksPath 設好之後回傳的就是 shared 目錄本身，會遞迴。
2. **repo 的 local `core.hooksPath` 會蓋過 global。** 查 stale 設定：
   `git -C <repo> config --local core.hooksPath`。

**為什麼搬**：原本三道住在 `lis-backend-emr-v2/.git/hooks/`（2026-06-26 起）。那個目錄不能
commit、瀏覽 repo 看不到、**重新 clone 就消失**——已經在 prod 出過事的規則，靠一個沒人看得到
也沒人拿得到的檔案在守。注意 per-repo 的 `core.hooksPath` 有一模一樣的毛病（它在
`.git/config` 裡），只有 global 設定才 clone-proof。
沒有把 hook commit 進 emr-v2：那是 team-owned repo，agent 自創慣例不進去（AGENTS.md 所有權層級）。

**同場發現**：`vibrant-america-working-agent` 的 local `core.hooksPath` 指著
`/Users/hung.l/src/lis-code-agent/.git/hooks`——七月改名時就刪掉的目錄。這個 repo 的 git hook
因此**靜默失效六週**，而且 local 蓋 global，不清掉就會一直失效。已 unset。

同期還有兩個 user-level hook（`~/.claude/hooks/`，2026-08-16 確認仍在）：
`skillsmp-reminder.sh`（UserPromptSubmit，週二/週五 LA 時間中午前第一次 prompt 注入提醒，
state 檔 `~/.claude/.skillsmp-reminder.last` 做每日去重）與 `skill-desc-opt-reminder.sh`。
前者取代了原本的雲端 routine —— Leo 嫌雲端要自己去頁面看、沒有 man-in-the-loop。

### daily-digest job 的運行環境（不只是排程時間）

- **launchd** `~/Library/LaunchAgents/com.lis.vibrant-daily-digest.plist`，本地時間 00:00
  （自動處理 DST，不會 UTC 漂移），`RunAtLoad=false`。雲端 routine 行不通：沙箱沒有 Leo 的
  憑證、讀不到 private repo、push 需要 GitHub App。
- **隔離**：跑在 git worktree `/Users/hung.l/.lis-daily-digest/main`，**絕不**在工作 repo 內跑。
  該 worktree 是 **detached HEAD**（2026-07-02 起沒有具名 branch），每次 run
  `git checkout --detach origin/main` 重新對齊，然後 `git push origin HEAD:main`（FF）。
- **半夜睡眠坑（已修）**：2026-06-24 首夜就失敗——機器睡著，剛喚醒時網路還沒起
  （claude `ConnectionRefused`）、keychain 還鎖著（`gh` token invalid）。修法：script 內建
  網路等待（最多 5 分）、`caffeinate -i` 防睡、`GH_TOKEN` 從 `~/.lis-daily-digest/.gh_token`
  （0600，`gh auth token` 匯出，繞開 keychain；`gh api` 與 `git push` 都吃這個 env）、
  claude 失敗重試一次。**`gh` 若重新登入導致 token 輪替，要重跑
  `gh auth token > ~/.lis-daily-digest/.gh_token`**，否則整條靜默失敗。
- **喚醒排程**：`sudo pmset repeat wakeorpoweron MTWRFSU 23:58:00`（2026-06-25 已設）。
  午夜需接電源；電池 + 闔蓋可能不醒 → 漏跑那一夜。
- digest 只掃各 repo 的預設分支，feature/staging 的 commit 不涵蓋。

### PNS / MyWellness 2FA email 的完整鏈路與 debug 入口

`收不到驗證信` 類問題的追法（2026-05-26 追 hrwilliams50@gmail.com 時逐段驗證）。

**鏈路**：patient-portal 前端 → coresamples-v2 gRPC `PatientService.PatientSendCreateAccountEmail`
（`LIS-backend-v2-coreSamples/service/patient_service.go`，產 OTP 存 Redis `code:email`，
TTL 10 分）→ HTTP `util.PnsSendCreateAccount2faAuthEmail` POST 到
`https://api.vibrant-wellness.com/v1/portal/trans-service/valogin/PnsSendCreateAccount2faAuthEmail`
（**部署路徑是 `trans-service`，不是 local repo 裡的 `trans-service-st`——部署的 code 有分歧**）
→ trans-service `valogin.controller.ts` → `pnsSend2faCodeEmail`（valogin.service.ts）發 Kafka
topic `Notification-Email-Template` 到 `vibrant-notification-events` Event Hub →
`noti/notification-center-deployment` consumer → Postmark。

**PNS 的信分散在兩台 Postmark server，查錯台就會得到「找不到」**：
- PNS **2FA 開戶/重設**（template 4059xxxx，Tag "PNS Two-Factor Authentication"）→ **ZymeBalanz (5595198)**
- PNS **kit 生命週期**通知（Tag `consume_pns*`，template 33xxxxxx）→ **LIS (8340335)**

查詢：`GET api.postmarkapp.com/messages/outbound?recipient=X&count=N&offset=0`
（**`offset` 是必填**，少了回 ErrorCode 700），再打 `/messages/outbound/{id}/details` 看投遞事件、
`/dump` 看原始 MIME。**用 recipient + Tag + Metadata 比對，不要用 bus 的 MessageID**——
Kafka/EventHub 訊息的 `MessageID`/`partitionKey` 是 producer 的 id，Postmark 送出時會給自己的。

**template id 的 remap 不是 bug**：consumer 依 `job.data.TemplateId` 分派——`zymeb[id]` 有值就
送 ZymeBalanz server 並換成 remap 後的 id（`/app/src/notification/ZymeBalanz-server.ts`，
例 `40591105→41526507` staging、`40591139→41526542` prod）。所以 trans 那個
`stprod ? 40591105 : 40591139` 的三元式**remap 完是對的**：真 prod 拿到 ZymeBalanz 41526542。
名字裡帶 "Staging" 的 LIS id 只是跨 server 命名交叉，prod 客戶收到的是 prod template。
（這條更正了早期「prod 用到 staging template / 2FA 是 raw HTML 寄的」的錯誤推論——Postmark 的
message-detail 對 template send 會回 `TemplateId=null`，正是那個 null 誤導出 raw-HTML 的猜測；
Metadata + 實際 render 出來的內容才證實是 template send。）

**四個會讓信靜默消失的坑**：
1. trans（`lis_front_logger`）與 coresamples（zap）的 log **只進 stdout**，沒有 DB、沒有 fluentd
   → 只能 `kubectl logs` 或 Log Analytics。
2. trans 的 `LoggingInterceptor` 在 RxJS `tap` 裡記 req+resp，也就是 **handler 跑完之後**
   → 一個 hang 住/逾時的請求在 trans **完全不會留下 log**。
3. coresamples 的 `PostJSON` 有 **30 秒 client timeout**，逾時就刪掉 Redis session 並回 500，
   **不寄信也不重試** → 短暫抖動會靜默吞掉驗證信。錯誤訊息是
   `context deadline exceeded (Client.Timeout exceeded while awaiting headers)`。
4. trans 的 `pnsSend2faCodeEmail` **每個請求**都做
   `Promise.all([localKafka.connect(), azureKafka.connect()])`，即使 `platform_type=cloud`
   （走 azure）也一樣 → **本地 Kafka（`default/lis-core-kafka`）掛掉會拖垮雲端寄信**，變成 30 秒逾時。
   2026-05-26 19:12–19:40 UTC 實際發生過（209 次 coresamples timeout；lis-core-kafka pod 19:30:19 被換掉）。

**要直接讀 bus**：`Notification-Email-Template` 是 `vibrant-notification-events` 上的單 partition
Event Hub，連線字串（SendListen）在 `LIS-transformer/.env` 的 `Azure_kafka_connection_string`。
用 `@azure/event-hubs` 的 `EventHubConsumerClient`（`$Default`、不 checkpoint）讀——AMQP
non-epoch 讀不會從線上 consumer 手上搶走 partition；**kafkajs 的 consumer-group 讀會觸發
rebalance 把 partition 搶過來，不要用**。

debug 存取（2026-05-26 本機驗證）：`kubectl` context `lisportalprod` 可用；pod 分別是
trans `default/lis-trans-deployment-*`（`SERVER_ENVIRONMENT=prod`）與 `-st`（stprod）、
coresamples `coresamplesv2/lis-coresamples-v2-deployment-*`、consumer
`noti/notification-center-deployment-*`。`az` CLI 的管理平面需要重新 MFA 登入才查得到 Log Analytics。

## 【journal 蒸餾 2026-08-16】本 repo 已知的明文憑證位置（未修，待 Leo 決定）

盤點自 auto-memory 遷移的 open finding，2026-08-16 dream 以 `git grep` 對 ground truth 覆核過。
記在這裡是為了**下次要動這些檔案時知道踩到什麼**，不是待辦清單——修法（改讀 env / 輪換密碼 /
清 git history）blast radius 各不相同，屬於 Leo 的決定。

1. **`lis_core_emr` 的 prod DB 密碼明文躺在 8 個 tracked 檔案裡**（`lisportalprod2` Azure MySQL，
   db `lis_emr`）。實測 `git grep -l '<pw>'` = 9 個檔案：`DailyJob/` 下 8 個
   （`hl7_triage_runner.py`、`hl7_triage_2026_05_30.py`、`run_triage.py`、
   `hl7_fail/run_triage.py`、`hl7_fail/triage_runner_2026-05-27.py`、
   `hl7_fail/triage_prompt.md`、`result_fail/result_fail_runner.py`、
   `vp17312_stageb/check_stageb.sh`）＋ `archive/native-auto-memory-workspace-2026-08-16/` 下 1 個。
   只有 `result_fail_runner.py` 走 `os.environ.get("LIS_DB_PASS", <literal>)`，其餘是無 fallback 的
   硬編碼常數——**所以「設個 env var 就好」對其中 7 個檔案無效**，要真的改 code。
   已經在 git history 裡，換掉檔案不等於換掉曝光。
2. **Cloud Report Service 的 OAuth client secret 明文進 repo**：
   `LIS-Report/base-report-server/deployment/azure/k8s-secret.yaml`（見上面 FHIR token 段）。

**通則**：這個 repo 是 private 但不是 secret store。要新增排程 job 時照 `result_fail_runner.py`
的 env 形式寫，且**不要留 literal 當 fallback**——留了 fallback，env 沒設時它會安靜地用明文跑，
於是「已經改成 env 了」這句話變成假的。

## 【journal 蒸餾 2026-08-18】斷言一個「守門 / 分支 / 設定」之前，先找到 writer，不是 reader（VP-9299）

VP-9299 當天寫進 STM 的四條「已查證事實」，被兩個獨立子 agent 一致推翻，四條的 root cause 是同一個：
**把「本機讀得到的 code / 檔案」當成執行時的真實狀態**。

| 我寫的 | 實際 | 為什麼讀 code 讀不出來 |
|---|---|---|
| `cheackRedisNolock` 守著「每 sample 一封信」 | 那函式**只讀不寫**，writer 兩處都被註解掉 → gate 是死碼、恆真 | 只找到 reader 就下結論 |
| 這是 beta 分支、只影響子集流量 | `let is_beta = true` 硬寫死，條件恆真 = 100% 流量 | 沒追賦值點 |
| helper 失敗回 `null` | 外層 catch 沒 `return` → 回 `undefined`；兩支 axios 都沒設 timeout | 只讀 happy path |
| `.env` 說 `envm="stprod"` | 線上值來自 ConfigMap（`envFrom: configMapRef`），`dotenv.config()` **不覆寫**已存在的 `process.env` | repo 檔案 ≠ 部署值 |

**可操作的規則**：
1. **Gate 要找 writer。** 看到 `if (checkX(...))` 形態的守門，先 grep 誰寫那個 key/flag。
   只有 reader 沒有 writer = 死碼，而且是最壞的一種——它讀起來像「dedup 存在」。
2. **`.env` 不是線上權威。** 任何 `process.env.X` 的行為推論，要對 deployed ConfigMap/Secret 查證
   （`kubectl -n <ns> get cm <name> -o yaml`）。這是核心原則 0「Sync With the World First」
   目前沒明講的一面：**deployed config 也是 world**。
   第 4 條實際帶出了 VP-17754：prod `envm=prod` 走 else 分支，`createConsumer` 硬寫
   `sessionTimeout: 45000` 並丟棄 caller 傳的 950000 —— staging (`stprod`) 看起來安全、prod 會 rebalance。
3. **子 agent 的結論也要當假設驗。** 兩個子 agent 都寫「Kafka 任何重投都會重寄信」，但
   `acquireEventLock` 寫的是永久 `trigger_history`（key 含 event_id），同訊息重投擋得住；
   真正的暴露是同 sample 的多個事件各發一封。轉述前沒複驗就會把錯誤放大成「兩方都這麼說」。

**舊分析的結論比事實更容易腐爛**：2026-06-06 那份 STM 的結構判讀全對（檔案、分支、TemplateModel），
只有行號位移；但兩個**結論**全錯，因為它把 V1 當成 V2 的同級 API。實際讀 `LIS-Report` 才發現
V1 handler 內部呼叫的就是 `getReportStatusListsByBarcodeV2`，只多做一次 `.map(p => p.report_name)`
——**V1 是 V2 的投影**，於是「Final-only filter 會讓清單變短、要問 PM」整個消失。
→ 舊 STM 的 `file:line` 可以當索引，**它的因果結論必須重推**；當初沒讀的上游 repo，兩個月後還是沒讀。

**dual-emit 的 key 要兩個都讀**：base-report 同時送 `report_status` 與長年 typo 的 `report_staus`
（PH-850 註解：7 個 repo 有 reader，rename 會**靜默**壞掉，所以雙寫）。
dual-emit 的意義就是讓 reader 遷移；**新 code 只讀 typo key 是在把債往前複製**。寫 `report_status ?? report_staus`。

**辯論的價值不在選 A 或 B**：它把人推去查一個原本沒想到要查的地方（這次是 prod ConfigMap）。
產出是三張 ticket（VP-17753/17754/17755）+ code 改動壓到只換 URL —— 因為辯論證明了 V2 helper 的
cache 與 retry 都是風險，**最小改動反而同時是最安全的改動**。

## 【蒸餾 2026-08-18】Clinical consult 的收件人 ground truth = `v2_calendar.calendar_owner_email`（copy-once cache）(VP-17759 / VP-17765)

同一週兩張 ticket（「確認信寄錯地址」與「additional notification email 收不到」）根因同一條：

**收件人解析鏈**：consult 的確認／提醒信寄給**病人角色 participant 的
`v2_calendar.calendar_owner_email`**。該欄位由 `createPatientCalendarForCustomerIfAbsent`
（LIS-transformer-v2 `provider-availability.service.ts`）在**首次 booking 時從 owner 的
provider/clinicadmin calendar 抄一次**，之後**永不再同步**。

- **booking form 打字輸入的 email 完全不會成為收件人**：它只以自由文字存進
  `v2_event.notes` 的 `[Email: ...]`，`CreateEventByPatientInput` 根本沒有 email 欄位
  → 沒有任何 payload 把它帶到後端。**是設計上被忽略，不是 bug**（VP-17759 的答案）。
- **staleness 規模**：practice 150105 的 15,389 個 patient-role calendar 中，
  **3,365 個（~22%）** 的 email 與同一 owner 現在的 provider calendar email 不同。
  VP-17765 的 provider 因此有 ~6 個月的提醒信寄給業務夥伴。
- **不要整批 resync**——那會把數千個收件人靜默翻成 practice 共用信箱。
  個案照 VP-17765 的做法做有界資料修正，系統性解法在 VP-17766（多收件人 To+CC 模型）。
- **comma fan-out 是未設計的 pass-through**：`calendar_owner_email` 塞逗號分隔多址，
  目前會原樣進 Postmark `To` 並正確送達（prod 實測），但沒有任何設計保證。

**又一個「找 writer 不找 reader」的實例**（同 VP-9299 那條）：writer 只在 calendar 建立時跑一次，
所以讀 dispatch 端的 code 永遠看不出值是哪來的、為什麼過時。

**診斷手法（<5 次查詢就收斂）**：Postmark 的 **per-recipient MessageEvents**
（同一封多收件人信裡每個地址各自的 Delivered/Opened）可以乾淨切開三種情況——
「根本沒被列入收件人」vs「列入但沒送達」vs「送達但當事人說沒收到」。
`v2_reminder_audit_log` 可獨立佐證同一事件歷來提醒實際寄給誰。

**流程教訓**：ticket 標題 ≠ 症狀。VP-17765 被 PM 寫成「Additional Notification Email」bug，
真正的症狀在 Zendesk 附件截圖裡，是另一回事。**附件一定要拉下來看**。

## 【PROMOTED 2026-08-18 · 跨 ticket 蒸餾】要證明「prod 上發生了什麼」，找只有那條路徑會寫的持久化證據（4 案）

2026-08-14~18 六張完成的 ticket 裡，有四張的決定性證據都是同一個形狀：
**不要用資料形狀去推論，去找那條路徑專屬的 persisted discriminator。**

| ticket | 問題 | 只有那條路徑會寫的東西 |
|---|---|---|
| VP-17714 | 是不是「換 clinician」造成錯 Zoom 連結？ | `v2_event_accession_audit_log.reason = 'clinician switch reschedule, original event N'`（`releaseForEvent` 寫的字串）撈出歷來全部 4 次 switch |
| VP-17715 | 這筆 result push 是機制自動送的，還是人工補送？ | **`bullmq_job_id`**：kafka 驅動的 record **必有**，人工 gRPC repush **必無**（`created_by=result_generation_service`）。08-17 那兩筆因此被正確判為人工補送、不算機制證明 |
| VP-17759 | 確認信到底寄到哪個地址？ | `v2_reminder_audit_log.recipient_email` —— 每次寄送逐筆寫入，帶 idempotency key 與 status |
| VP-17765 | 是「沒被列為收件人」還是「列了但沒送達」？ | Postmark **per-recipient** MessageEvents（同一封多收件人信裡每個地址各自的 Delivered/Opened） |

**反例（同樣出自 VP-17714）**：`v2_event_participant.created_at` **不能**用來反查原地換人——
`replaceEventParticipants` 是 deleteMany+createMany，任何帶 participants 的 update 都會重寫它。
**寫入端有沒有留下只有這條路徑會產生的字串/欄位，決定了事後可不可稽核。**

**推論**：設計新流程時，若某個分支未來會需要事後證明「它跑過」，就得在那個分支寫一個獨有的
持久化痕跡。事後補不回來——VP-17714 能查是因為 `releaseForEvent` 剛好寫了那句 reason。

### 同批的第二個系統性觀察：抓到事實錯誤的是外部挑戰，不是自我複查

- VP-9299 自評信心 3/5：「四條事實誤述是被 Leo 要求的辯論擋下來的，**不是自己抓到的**」。
- VP-17714：「Leo 的兩次回問各修正一個錯誤」——第一次逼出 FE 兩段式的方案（原本四案的漏洞），
  第二次逼出殘留路徑與外部配合項。
- 兩次都是**在呈報給 Leo 之後**才被推翻，代表自我複查那一關沒有攔截力。

→ 對「守門 / 分支 / 設定 / 誰收到」這四類斷言，把「找 writer」與「找專屬痕跡」當成**交付前的檢查**，
不要等辯論或 review 才觸發。VP-17714 另有一條值得保留的自律：
**自己提的反對理由查不實，要主動撤回**（擔心錯連結外溢到 Google/Outlook → 查完發現 150105
根本沒有該 integration、歷來 0 筆同步，回報時明講這條不成立）。

## 【EXTRACTED 2026-08-19 · VP-17752】「Alerting 存在」不等於「alerting 會響」

- **prod 的 `SENTRY_DSN` 從未設過**：VP-17544 把 order-abandonment 上報寫好、測綠、部署——但 DSN
  只進了 STAGING ConfigMap。AKS 與 on-prem 兩個 prod pod 每次開機都 log
  `SENTRY_DSN not configured — error reporting is disabled`，講了好幾週沒人讀。
  **prod 從來沒有任何一則 order-abandonment alert 響過**，這就是 hl7_file_input 6848/6556
  隱形六天／一個月的全部原因。
- 修法（2026-08-18，已完成）：DSN + `SENTRY_ENVIRONMENT=production` 寫進三份 ConfigMap
  （AKS default ns 的 Jenkins-sync 副本、AKS emr-v2 ns、on-prem），pod 重啟後**從 pod 內
  發真實 test event 拿回 HTTP 200 + event id 才算通**（`failure_class=channel_test`）。
  `Sentry initialised` 只代表 DSN 能 parse，不代表通。
- **檢查程序**：信任任何 alert path 之前——(1) 讀 pod 自己的 startup line；(2) 從該環境發一則
  真實 event 走完全程。這是 Hot lesson「Channel liveness is third-party state」的 config 變體。
- **同形事故**：VP-17559 的 Key Vault break（staging 驗過、prod 假設會通）。
  **在容易的環境驗過 config，不能推定另一個環境也有**——staging/prod ConfigMap 是兩份實體。
- 殘留：`SENTRY_DSN` / Kafka SAS 搬 Key Vault = VP-17756；Sentry 端 alert rule（依
  `failure_class` 路由給 PM）未設，Leo 已知。

## 【EXTRACTED 2026-08-19 · LIS-7690】emr-v2 / on-prem 操作 gotchas（全部 probe 實證）

- **fresh worktree push 必撞 pre-push hook**：`.git/hooks/pre-push` 跑 `npx prisma generate`，
  沒 `node_modules` 時 npx 抓 Prisma 7.x，會拒絕 repo（pin ^6.15）的 `datasource.url`（P1012）。
  解法：用 pinned binary 驗（`node_modules/.bin/prisma validate` + dummy `DATABASE_URL`）再
  `--no-verify` push。
- **appserver04（192.168.60.5）只收密碼 auth，key auth 真的被拒**——歷來所有 BatchMode 失敗
  都是這原因，不是不通。macOS 無 sshpass，用 `/usr/bin/expect` + env var 帶密碼。
  完整 recipe + 密碼在 `~/src/credential/onprem-appserver-ssh.md`（不入 repo）。
  kubectl 在 appserver04 `/usr/local/bin/kubectl`（k8s v1.22.3，6 nodes = 192.168.60.2-7）。
- **on-prem ConfigMap 是明文 secret 庫**（prod DB URL 含密碼、JWT_SECRET、Kafka SAS、
  `VIBRANT_API_TOKEN`）——查值用 `-o jsonpath` 指定 key，**絕不 grep 整份 yaml dump**。
- **emr-v2 的 `/health` 無法辨識環境**：`environment` 欄位是 `NODE_ENV`，staging pod 也回
  `production`；真值在 `ENVIRONMENT`/`SERVER_ENVIRONMENT` env。`SWAGGER_ENABLED=false` 沒接線，
  `/api/docs` 照樣 200。
- **live cluster 有 repo 裡不存在的物件**：emr-v2 兩條 short-path ingress（order/fhir）、
  transformer-v2 的 Service+Ingress 全都只在 cluster 裡。**寫 endpoint 文件 / 查路由一律
  probe live cluster，不能只讀 repo yaml**。
- **on-prem prod image tag 是 `:latest` 非 SHA-pinned**——INCIDENT-20260817 十三天 silent drift
  的結構性成因，尚未修。
- emr-v2 auth 兩條路（`jwt.strategy.ts`）：內部 HS256（可自組，secret 在 prod ConfigMap；
  mint 工具 + 說明在 `~/src/credential/emr-v2-jwt-signing.md` / `mint-emr-v2-token.py`，
  驗 token 用 `integration-management/health`——`@SkipDataAccessCheck` + read-only）；
  partner FHIR RS256（私鑰在 OAuth service，不可自組）。secrets 一律留在 credential 目錄，LTM 只記指標。

## 【EXTRACTED 2026-08-19 · RESULTCHECK】report-status API 的 token 前綴 + sandbox 連 prod DB

- `getReportStatusListV2` / `testHierarchyForReports`：`Authorization: <token>` **RAW，
  不加 Bearer**——加了直接 401。（對照：`getLegacyBundleMapping` 用 ORDER_API_TOKEN 時**要** Bearer；
  同一個 pricing endpoint 用 VIBRANT_API_TOKEN 時又拒絕 `bearer `。每個 endpoint 記各自的前綴，別類推。）
- 從本機 sandbox 連 prod `lis_emr`（lisportalprod2）現在強制 TLS：mysql2 要帶
  `ssl:{rejectUnauthorized:false}`，否則 `--require_secure_transport=ON` 直接拒連。
- on-prem coresamples gRPC `192.168.60.6:30276` 從本機 ECONNREFUSED 時，cloud
  `10.224.0.199:30276` 是可用替代。
