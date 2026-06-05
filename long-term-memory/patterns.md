---
id: patterns
type: ltm
category: repo_patterns
status: active
score: 0.1386
base_weight: 0.8
created: 2026-04-22
updated: 2026-06-02
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

### mysql2 Timezone
- Legacy MySQL datetime 欄位存 UTC 但無 timezone info
- mysql2 連線必須加 `timezone: '+00:00'` 才能正確讀取 UTC 值
- 不加的話預設用本機時區（如 PST）解讀，導致時間偏移

### DB UPDATE transaction 加 pre-check sanity guard
對 prod DB 跑 UPDATE/INSERT 前，在同一 script 先 SELECT 當前狀態並比對預期值（e.g. `integration_type === 'RESULT_ONLY'`、`emr_name === null`、target row 仍存在）。不符就 throw、阻擋 transaction，避免 STM/分析跟 DB 真實狀態之間的時間差導致誤改。配合 `prisma.$transaction` rollback 可全套保護。範例：VP-16396 的 `_apply-vp16396.ts` 在 ehr_integrations / order_clients / sftp_folder_mapping 三表分別 SELECT 比對後才執行兩條 UPDATE。

### 複雜 service method 的 auth-path unit test
測試一個會觸發大量 downstream 邏輯的 service method 的授權前段時，用 `jest.spyOn(service as any, '<downstream-private-method>').mockResolvedValue(...)` 短路後續流程，只跑授權檢查再立即 return。避免 mock 整條 pipeline（prisma transactions、kafka publish、email service…）。範例：LIS-transformer-v2 的 `updateEventByPatient` 測試 spy `updateWholeEventRecord` / `mapEventToGraphQL` / `buildWholeEventUpdateData` / `resolveRecurringEditScope`，使 happy-path 測試短小可讀（VP-16361）。

### order_clients 無 updated_at 欄位
`lis_emr.order_clients` schema **沒有 `updated_at` 欄位**（不像 `ehr_integrations` 有）。寫 raw `UPDATE order_clients SET ... updated_at=NOW()` 會 fail with `Unknown column 'updated_at' in 'field list'`。寫 SQL 前先驗 schema，或避開 updated_at。完整欄位：id, customer_name, customer_id, customer_provider_NPI, customer_practice_name, clinic_id, kits_options, emr_name, remote_folder_path, old_clinic_id。

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
- **典型症狀**：FE call 該 table 的 endpoint 回 500、staging pod log 印 `prisma:error P2021 ... does not exist in the current database` (INCIDENT-20260528 reject endpoint 案例)
- **長期 fix**：把 migration apply 寫進 Jenkinsfile pre-deploy step（同時對兩個 DB 跑），不再靠人記得

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

任何 host reachability check 都先 `SELECT host, port FROM emr_sftp_source WHERE emrName=...` 取真實 port。

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

### Silent .catch swallow 反 pattern
`event.service.ts:1574` 用 `.catch((error) => logger.error(...))` 吞 exception → 任何 email 失敗 silent，前端成功但 email 沒寄出，無 audit trail。`email_send_out_request` / `event_notification` 兩張 audit 表存在但 transformer-v2 無寫入碼。後續做 audit log feature 時要避免重蹈。

### Email 時間 timezone 地雷三連
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
