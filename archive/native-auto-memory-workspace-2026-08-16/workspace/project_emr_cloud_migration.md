---
name: project-emr-cloud-migration
description: "EMR v2 (lis-backend-emr-v2) on-prem → Azure AKS migration — status, decisions, verified infra facts"
metadata: 
  node_type: memory
  type: project
  originSessionId: 37705de5-a5b9-4549-b1be-2b522e1b4b48
---

lis-backend-emr-v2 正從 on-prem（appserver04，pod 用 nodeName pin + hostPath PV，與 v1 Java 共用 `/mnt/storage/EMR_storage`）遷到 Azure AKS（context `lisportalprod`，pod CIDR 10.224.x.x）。狀態截至 2026-05-27：

**已驗證的事實（這次實測）**
- AKS pod → 地端 192.168.x.x **全通**（gRPC `192.168.60.6:30276`、Kafka `192.168.60.9-11:9095`、ClickHouse `192.168.62.85:8123` 都 OK）→ 有專線；雲端 pod 可直接 call 地端，Kafka/Redis 上雲都可先不做。
- Azure Files storage 權限 OK：`azurefile-csi`（standard）動態 PVC 能 Bound + RWX 讀寫（busybox 測過）；目前全 cluster 0 個 azurefile PVC，EMR 會是第一個。
- Leo 個人 Azure 帳號 RBAC 僅 "AKS Contributor" scoped 到 managedClusters/lisportalprod，**看不到 node RG（MC_lisportalprod_...）的 storage account / file share**；動態 provision 靠的是 cluster managed identity，不是他帳號。az ARM 列 storage account / RG 都空。
- 雲端 ingress 慣例：host `api.vibrant-america.com`、path `/<ver>/<domain>/<svc>(/|$)(.*)` + `rewrite-target /$2`（strip 前綴）。repo 的 `k8s/base/ingress.yaml`（`api.vibrantamerica.com` 無連字號）是過時的。

**已決定**
- v1 Java 這幾天會完全退場 → hostPath 共用問題消失，HL7 可純雲端存。舊檔不搬，只要新檔進雲端。
- Storage 傾向 **option A（動態 azurefile-csi PVC）**，Leo 2026-05-28 會再確認後才動。
- URL **design B**：移除 app `setGlobalPrefix("api/v1")`，ingress 前綴 `/v1/lis/emr-service` → 對外 `https://api.vibrant-america.com/v1/lis/emr-service/<path>`。

**產出 / 進行中**
- Migration doc（API base URLs + affected endpoints + outbound deps）已發布在 Leo 個人 Confluence space：pageId 2457108486（`/wiki/x/BoB0kg`）。Kristine 開 ticket 已開出 VP-16784/85/86/87（5/28 起）。
- Design B 衍生實作（還沒做，等開 ticket）：移除 global prefix、health probe `/api/v1/health`→`/health`、重寫 ingress.yaml、image→ACR、通知 consumer。

**2026-05-28 verification（Leo 離席期間 autonomous）— 詳見 STM VP-16784-87**
- **VP-16784/85/86/87 對 EMR repo no-op**：EMR 沒有 client code 呼叫 shipping/audit/dashboard/issue RPC（grep `src` 無匹配；那 4 個是 LIS-transformer-v2/Calendar 使用）。我不跨 repo 動工，等 Leo 指示再做 LIS-transformer-v2 那邊。
- **Kafka cloud-first refactor 已 commit（2026-05-29，branch `feature/leo/kafka-cloud-primary` commit `71e4cfe`，local 未 push）**：
  - `kafka-report-finished-listener.service.ts` 改成 cloud-first + on-prem fallback。`KAFKA_CLOUD_ENABLED` default 'true'，失敗自動退回 on-prem。
  - 新 env vars: `KAFKA_CLOUD_BROKERS=general-events.servicebus.windows.net:9093` / `KAFKA_CLOUD_TOPIC=general-sample-events` / `KAFKA_CLOUD_SASL_USERNAME=$ConnectionString` / `KAFKA_CLOUD_SASL_PASSWORD=""`
  - repo yamls 是 `.gitignore`d 不會 commit；真 ConfigMap 在 Azure AKS 上，Leo 要 `kubectl edit configmap lis-emr-v2-config-prod` 加新 keys + 填真 password（從 Event Hub `general-events` namespace `RootManageSharedAccessKey`）
  - 順手修 pre-existing spec TS2554（agentResultService 4th arg + processForAgent mock）— staging 上也壞，跟我這次無關但同時清掉
  - build ✓ / spec ✓
  - 安全：即使 ConfigMap 沒更新就 deploy，PASSWORD 空 → `buildCloudKafkaConfig` return null → 自動 fall back on-prem，pod 仍可起來
- **Kafka 兩條路都可（重要更正 2026-05-28 深夜）**：
  - 之前判斷「Kafka 不該遷」**部分翻案** — empirical 證實 cloud Event Hub `general-events/general-sample-events` 跟 on-prem `lis-general-events` 是**同一份 stream dual-published 到兩個 cluster**（timestamp-aligned 4hr 窗口，event_id 交集 8 個 + millisecond timestamp byte-identical）。
  - 所以 EMR 上 AKS 後 Kafka 配置有兩個合法選項：
    - **A. 留 on-prem brokers (`192.168.60.9-11:9095`) over VPN**：code 不動，配置不變。AKS↔on-prem 跨網路 ehr-chat/ehr-workflow 已 production-proven。kcat 從 AKS pod 實測 metadata + consume 全通，advertised.listeners 回 192.168.60.x:9095 同 bootstrap 無 DNS 問題。
    - **B. 切 cloud Event Hub `general-events.servicebus.windows.net:9093` + SASL_SSL**：因 dual-published，**不需 producer 端協調**（這推翻先前說「producer 也得遷否則收不到」的判斷）。code 改：KafkaJS 加 `ssl: true` + `sasl: {mechanism: 'plain', username: '$ConnectionString', password: <conn string>}`、KAFKA_BROKERS 換 EH endpoint、KAFKA_TOPIC 從 `lis-general-events` 改 `general-sample-events`。consumer group offset 跨 cluster 不 carry over，但 EMR `fromBeginning: false` 影響很小。
  - **不急遷 cloud**（A 可行），長期解耦 on-prem 依賴可選 B。
  - 我前後三度翻轉（dual→獨立→獨立→dual）的根因：多 partition / 流量懸殊 topic 比對必須用 `kcat -o s@<ms>` timestamp seek 對齊 wall-clock 窗口；前兩次用「最新 N 條」造成 false negative。教訓記入 patterns.md。
- 4 cloud endpoint TCP+gRPC handshake 都通；reflection 沒開、proto byte-equivalence 未驗（需上游 .proto），但 EMR 不用這些 RPC 所以無實質影響。

**2026-07-01 update — Phase A tickets created + PARITY MANDATE (Leo)**
- Leo 硬要求：遷雲是**純 lift-and-shift，所有 endpoint/pipeline 行為必須跟本地一模一樣**。這推翻 design B 的「移除 `/api/v1` global prefix」——移掉會讓 pod 路徑從 `/api/v1/result` 變 `/result`＝破壞 parity。**Phase A 決定：`main.ts setGlobalPrefix('api/v1')` 保留不動**，改在 ingress 用 `rewrite-target: /api/v1/$2`（對外 `/v1/lis/emr-service/...` → pod `/api/v1/...`）。印證：on-prem prod deployment 的 probe 仍是 `/api/v1/health`（prefix 從沒真的拿掉）。
- **k8s/base/deployment.yaml 不符合 parity**：沒有 Redis sidecar、也沒有 `/EMR_storage` 掛載（但 config 要 REDIS_HOST=localhost + HL7_LOCAL_ROOT=/EMR_storage/…）→ 直接用會壞。parity 正解：以能動的 `azure-lis-emr-v2-deployment-prod.yaml`（on-prem，有 redis sidecar + emr-pv-claim 掛載 + replicas:1）為基準。
- **Tickets**（都 assign Leo）：Epic **VP-17291**（Phase A single-replica lift-and-shift）；A1 **VP-17292** deployment、A2 **VP-17293** Azure Files PVC、A3 **VP-17294** ACR、A4 **VP-17295** secrets/configmap(+staging DB)、A5 **VP-17296** ingress(keep /api/v1)、A6 **VP-17297** cutover+parity 驗證。**Phase B（多 pod：shared Redis + POD_ROLE intake/pusher split + HPA）明確排除**（會改行為，另立；跟 VP-17217 SFTP pod-role gap 同批）。
- **A1 DONE**：`azure-lis-emr-v2-deployment-aks-prod.yaml`（新檔，不動 on-prem 那份）= on-prem-prod 去 nodeName + image→ACR + imagePullSecret + POD_ROLE=all 明寫；redis sidecar/replicas:1/env/port/probe 全留。branch `feature/leo/VP-17292` commit 6b923de（未 push）。
- 現況補：BullMQ 用 REDIS_HOST（localhost sidecar）→ 多 pod 會斷佇列，這是 Phase B 要 shared Redis 的根因。DATABASE_URL：prod 已 Azure（lisportalprod2），staging 仍 on-prem 192.168.60.11（A4 處理）。v1 Java 已於 2026-06-10 退場（見 [[project-emr-backend-retired]]）。
- Sandbox 限制：能寫 manifest，但 kubectl apply / ACR push / 真 secrets / cutover 需 cluster+Azure 權限（做不到）。

- **A2 + A5 DONE**（同 branch feature/leo/VP-17292）：`azure-lis-emr-v2-storage-aks.yaml`（PVC emr-pv-claim RWX azurefile-csi 50Gi）+ `azure-lis-emr-v2-ingress-aks.yaml`（ClusterIP svc selector lis-emr-v2-prod http80→3000/grpc5000 + nginx ingress host api.vibrant-america.com path `/v1/lis/emr-service(/|$)(.*)` rewrite `/api/v1/$2` TLS vibrant-tls-secret；CORS 留給 app、gRPC 不走 ingress）。commits 5fba849/7f6e995。**PR #218 → staging**（A1+A2+A5）。ingressClassName=nginx 待對 live cluster/trans-v2 確認。

- **A6 checklist DONE**：`docs/EMR-AKS-A6-PARITY-CHECKLIST.md`（parallel-run diff runbook）→ **PR #219**（branch feature/leo/VP-17297）。
- **A3/A4 prep DONE + 重要 discovery**（PR #220，branch feature/leo/VP-17294）：
  - **A3 ACR push 其實已存在**：main branch Jenkinsfile 尾段已 `docker login lisportalprod.azurecr.io` + tag/push `:${GIT_SHA}`+`:latest`（標「optional/future cloud」）。→ image 已進 ACR。
  - **A4 AKS ConfigMap 已存在**：Jenkinsfile 是**從 AKS 拉** lis-emr-v2-config(-prod) 再套 on-prem。secrets 目前放在 ConfigMap 內（prod deployment 只有 envFrom configMapRef、無 secretRef）。
  - **真缺口**：Jenkinsfile **只部署 on-prem**（scp 192.168.60.6 + kubectl apply on-prem yaml），**沒 apply 到 AKS** → 補一個 gated（default off `DEPLOY_TO_AKS`）的 AKS-deploy 片段（doc 裡，未動 live pipeline）。
  - ⚠️ **資安**：Jenkinsfile 有**明碼 registry 密碼**（on-prem + ACR admin），已在 git 歷史 → 建議輪替 + 搬 Jenkins credentials。
  - 產出：`docs/EMR-AKS-A3-A4-PREP.md` + `azure-lis-emr-v2-configmap.template.yaml`（sanitized，密碼 placeholder）。
- **Phase A PRs（都 → staging，未 merge）**：#218（A1+A2+A5 manifests）、#219（A6 checklist）、#220（A3/A4 prep）。

**2026-07-01 — 實際部署到 AKS（VERIFY MODE，可跑 kubectl，Bash 就在 Leo 機器上、kubeconfig=lisportalprod）**
- **cluster 慣例（實查 transv2）**：每服務自己 namespace；api.vibrant-america.com 用 ingressClass `webapprouting.kubernetes.azure.com`（`nginx` class 是舊 api.vibrant-wellness.com）；TLS 用 cert-manager cluster-issuer `letsencrypt` + per-ns `tls-secret`；**ACR 已 attach → deployment 不需 imagePullSecrets**（拿掉了）。→ #218 manifest 已改成 namespace `emr-v2` + webapprouting + 無 imagePullSecrets。
- **已 apply 到 emr-v2 ns**：Namespace、PVC emr-pv-claim（**Bound**, azurefile-csi RWX 50Gi）、Service（3000/5000）、Ingress（LB 20.106.115.138）、Deployment（**verify mode**：`POD_ROLE=pusher`+`ENABLE_KAFKA_CONSUMER=false` → 不抓 SFTP、不吃 Kafka，log 已證實，**不會跟 on-prem 重複處理**）。committed manifest 仍是 POD_ROLE=all 供 cutover。ConfigMap lis-emr-v2-config-prod 已從 default 複製到 emr-v2。
- **端點確認跑在 AKS**（經真實 ingress LB 打）：`/v1/lis/emr-service/health`→200（AKS pod）、`/result`+`/grpc-v2/status` 無 token→401（app 回的）→ rewrite `/api/v1/$2` 正確。swagger `/api/docs` 走 ingress 會 404（在 /api/v1 prefix 外，rewrite 加了 prefix；小副作用）。
- **TLS root cause + 修法**：cert 卡住是因 cert-manager 的 HTTP-01 solver ingress 落在錯 class/LB（solver pod 根本沒起）。修：(1) 從 tls hosts 拿掉不擁有的 `webapprouting.kubernetes.azure.com`；(2) 加 `acme.cert-manager.io/http01-edit-in-place: "true"`（challenge 直接掛本 ingress，已在對的 LB）→ **cert 變 Ready True（真 LE 憑證，到期 2026-09-29）**。lis-results 也有同樣半發問題。
- **重點**：直接打 LB IP、SNI api.vibrant-america.com 供的是 nginx **fake cert** → 真 client TLS 在 **Azure 邊緣終結**，我們的 path 沿用該 host 既有公開憑證，cutover TLS 不是問題。
- verify pod 留著跑；秒退 `kubectl delete ns emr-v2`。

**2026-07-01 — parity 驗證 + 真送 + CICD**
- **端點 parity（帶 admin token, on-prem vs AKS via ingress LB）**：33 無參數 GET → 30 逐字節相同；3 個 DIFF 全是 verify-mode（pusher）造成（/sftp/status 沒連 SFTP、/scheduled-reports cron 少 hl7-order-fetch）→ cutover POD_ROLE=all 會一致。帶參數 GET（2573863）3/3 相同。使用者無法分辨。
- **result 產生 parity**：generate-content/2573863 兩邊 HL7 **byte-identical**（223 segments，只差產生時間）。
- **真送 2573863（AKS，授權）**：`POST /result/generate/2573863 {send_result:true}` → 產 HL7 → 寫 PVC → **SFTP 傳到 vendor MDHQ /bliemr/results/**，狀態回 TRANSMITTED。**客戶收到測試。單筆發送在 AKS 完全可行。**
- **發現既有 bug VP-17302**：`POST /result/generate/batch` 兩環境都 500（`generate/:sampleId` 路由遮蔽 `generate/batch`）→ 已修（reorder route，literal 在 param 前）+ supertest routing 測試。**PR #221**（branch bugfix/leo/VP-17302）。非遷移造成。註：8 個 result service spec 在 main 上本來就因測試 fixture TS 型別漂移而 fail，與此無關。
- **generate-content 有副作用**：會寫 DB（把 transmission record 設回 PENDING）；不是純唯讀。
- **CICD**：Jenkinsfile 現在 main build 已 push ACR + 只部署 on-prem。加了 **gated（`DEPLOY_TO_AKS=true` 預設 off）AKS-apply stage**（在 lisportalprod withKubeConfig block 內：套 emr-v2 configmap + storage/ingress/deployment + rollout）→ **PR #220**。end state（全自動雲端）= cutover 時開 flag + on-prem 縮 0 + 之後移除 on-prem 部署 block。

**2026-07-01 — 架構定案：endpoints 上雲、pipeline 在地（Leo）**
- 新 `POD_ROLE=web`（`src/config/pod-role.ts`）：只服務 HTTP/gRPC endpoint，isIntake=isPusher=false → 不跑 HL7 fetch cron / BullMQ worker / kafka consumer / 排程報表。AKS deployment 改成 `POD_ROLE=web` + `ENABLE_KAFKA_CONSUMER=false`；on-prem 維持 `POD_ROLE=all` 跑 pipeline。**兩邊並存不會重複處理**（不用 on-prem 縮 0）。
- ⚠️ 舊 image（無 web enum）遇到 POD_ROLE=web 會 fallback 'all'（跑全部）→ **web 只在新 image 部署後才安全**。目前 AKS verify pod 是舊 image + pusher+kafka-off（安全），真 web 要等 main merge 出新 image。
- **整合成單一 PR #222**（branch feature/leo/emr-aks-phaseA → staging）含：AKS manifests(namespace emr-v2/webapprouting/cert-manager TLS/no imagePullSecrets)、POD_ROLE=web、Jenkinsfile gated AKS deploy(DEPLOY_TO_AKS)、batch route fix(VP-17302)、docs。舊 PR #218/#219/#220/#221 已 close（superseded）。build+31 tests 綠。
- **Confluence before/after doc**：pageId 2525069319（在 folder 2524971020）— before `http://192.168.60.5:31318/api/v1/…` → after `https://api.vibrant-america.com/v1/lis/emr-service/…`，只換 base URL、auth 不變、parity 已驗證。
- **Deploy 計畫**：merge #222 → staging → main（main build 出含 web 的新 image 到 ACR + on-prem 部署不變）→ 設 DEPLOY_TO_AKS=true 或手動 kubectl apply AKS manifests（POD_ROLE=web 新 image）→ consumer 換 base URL 到雲端。ingress 路徑 /v1/lis/emr-service 已在 webapprouting LB（api.vibrant-america.com 解析到那），不需另改 DNS。

**2026-07-02 — Phase A 上線完成 + Phase B 開票**
- **Cloud live 驗證**：AKS pod image 已 pin GIT_SHA（`:3bf84c9b…`，digest dbda01ee）、POD_ROLE=web + ENABLE_KAFKA_CONSUMER=false（pod env 實查）、TLS Ready、health/result/grpc-v2/batch 全通。CICD `DEPLOY_TO_AKS`（booleanParam，現 default true）自動 deploy 驗證 OK（AKS apply 在 ACR push 之後、image pin sed GIT_SHA、rollout timeout 420s）。
- **batch upload 定案走 cloud**（Leo 選 Option A）：「transmission 在 on-prem」只指自動 pipeline；**endpoint 觸發的傳輸（含 /result/generate/batch、send_result:true）在雲端是合法的**。gRPC `192.168.60.6:31317`（on-prem NodePort→5000, GenerateBatchResultsHl7）不用改——建議 caller 改用 cloud HTTP batch endpoint（雲端 gRPC 5000 沒對外：ClusterIP + ingress 只轉 HTTP 3000）。
- **雲端監視 pattern**：告警只盯自動 pipeline 標記（Hl7OrderFetch/process-hl7-file/ResultGenerationProcessor/kafka eachMessage/排程報表），endpoint 觸發 TRANSMITTED/sftp 不告警；kubectl 空回應=暫時性失敗要跳過（曾誤報一次）。
- **Phase B 開票 VP-17312**（standalone Story 無 Epic — Leo 要求「只要 story + QA」；QA=**VP-17313**(Test type, `is tested by` link, Pre-Conditions 欄位必填≤255字)；assign Leo，低優先無期限）：pipeline 上雲 = 硬切換（絕不雙跑），6 前提：①防雙跑 ②vendor SFTP allowlist AKS egress IP（主要 blocker，對外協調）③intake/pusher split 或 connection pool ④shared Redis ⑤AKS→Kafka/core gRPC 驗證 ⑥排程報表單一 leader。
- **on-prem endpoints 保留 2 週後退場**（公告已擬，英文，doc 連結 tiny `/wiki/x/B4CBlg`＝pageId 2525069319 v3）。doc 仍在 Leo 個人 space，搬團隊 space 未決。

**（舊）all-role cutover 步驟（已被 web 架構取代，保留參考）**：把 verify pod 轉正（POD_ROLE=all + ENABLE_KAFKA_CONSUMER=true）**同時** on-prem 縮 0（避免重複處理）→ 導 api.vibrant-america.com/v1/lis/emr-service 流量 → soak → 拆 on-prem。⚠️ 千萬別 all-role 與 on-prem 並存。

**仍 pending（需 Azure/cluster 權限，sandbox 做不到）**：實際 ACR push 轉正 + 建 azure-registry-secret/vibrant-tls-secret + kubectl apply AKS manifests + A4 config parity audit/staging DB + 跑 A6 cutover 驗證。Redis/多 pod = Phase B deferred。輪替明碼 registry 密碼。

相關：[[reference-azure-mysql]]、[[reference-pns-2fa-email-pipeline]]、[[feedback-reference-lis-code-agent-first]]、[[feedback-api-doc-format]]、[[feedback-end-to-end-equivalence]]。lis-code-agent STM/LTM 有 VP-16685（cloud migration）、VP-16784-87（4 RPC + Kafka verification）、INCIDENT-20260518（Azure Redis 不可達）、VP-16463（deploy chain 教訓）。
