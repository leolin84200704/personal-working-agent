# Work Contribution — VP-17217: emr-v2 SFTP singleton contention

> Repo: `lis-backend-emr-v2` ｜ Ticket: VP-17217 ｜ Date: 2026-06-25
> PRs: #196 (Phase 1) · #198 (Phase 2a) · #201 (Phase 2b)
> Related incidents: INCIDENT-20260601-sftp-hang, INCIDENT-20260604-mdhq-stale-connections

---

## TL;DR
emr-v2 線上 result 報告「發不出去 / 卡住」，root cause 是 **一個全 pod 共用、且沒有並發保護的 `SftpConnectionService` singleton**。任何兩件 SFTP 工作時間上重疊，後者的 `connect()` 會把前者正在用的連線砍掉。分三階段修：(1) inbound/outbound 拆連線、(2) inbound 同 host 連線重用、(3) outbound 上傳序列化。實測 `Unexpected end event` 6000/天 → 0、連線數 172/tick → 25。

---

## 問題（Problem）

### 症狀
- 批次送 result（~170 筆）整批爬不動、卡數小時。
- 報告上傳到 vendor SFTP 後 gRPC `GenerateResultHl7` 遲遲不 return。
- `result_transmission_records` 失敗數看似持續增加。
- SFTP log 單日 6000+ 次 `getConnection: Unexpected end event`（對 MDHQ `34.199.194.51:2210`）。

### 根因（單一本質問題）
`SftpConnectionService` 是 NestJS `@Injectable()` 預設 **singleton**，整個 pod 只有一份共用 `this.client`，而且：
```ts
async connect(config) {
  await this.safeDisconnect();   // 任何人連線前，先把現有連線強制關掉
  ...
}
```
且**完全沒有 mutex / 序列化**。所有使用者（inbound order-fetch、outbound result-push、scheduled reports、SFTP 測試端點）共用這一條連線。

→ 只要有兩件 SFTP 工作重疊，後進來的 `connect()` 就 `safeDisconnect()` 掉前者正在 `put()`/`list()` 的 socket：
- 上傳的 `put()` 等不到 vendor 的 `SFTP_FXP_STATUS` ACK（bytes 已 flush，**檔案會出現在 vendor**，但 ACK 永遠回不來）→ hang 到 10 分鐘 timeout。
- 連線被中途砍 → `Unexpected end event`。

### 放大因子
- **order-fetch cron**：`@Cron` 每 15 分鐘對 ~200 個資料夾**逐個** connect/disconnect。MDHQ 把 ~172 個租戶資料夾放在**同一台 host** → 一個 tick 對同 IP 爆 ~172 次連線 → 踩 vendor（Bitvise WinSSHD）的 **per-IP 連線上限** → 被拒/斷 → 自動 retry 3 次 → 越斷越重試（惡性回圈）。
- **POD_ROLE 分流沒生效**：code 本有 `intake`/`pusher` 分流設計，但兩個 on-prem pod 都 `POD_ROLE` 未設(=all)、且 `REDIS_HOST=localhost`（各自 sidecar、不共用），分流靠共用 Redis 當 intake→pusher 橋樑 → 直接設 env 分流會斷自動結果路徑，救不了。

---

## 解決方案（Solution）

三個 Phase 都在解「一份共用連線、無並發保護」的不同面向。**刻意不用 connection-level mutex**：`SftpController` 把 `connect()`/`disconnect()` 開成兩個獨立 HTTP endpoint，「拿鎖在 connect、放鎖在 disconnect」一旦有人只 connect 沒 disconnect 就**全 pod 死鎖**，比原問題更糟。

### Phase 1 — inbound / outbound 拆成兩條連線（PR #196）
用 DI 額外註冊**第二個** `SftpConnectionService` + `SftpFileService` 實例（custom provider token `INBOUND_SFTP_CONNECTION` / `INBOUND_SFTP_FILE`），讓 `Hl7OrderFetchService` 注入這組專屬實例：
```ts
// sftp.module.ts
{ provide: INBOUND_SFTP_CONNECTION, useClass: SftpConnectionService },                       // 同 class，獨立 instance
{ provide: INBOUND_SFTP_FILE, useFactory: (c) => new SftpFileService(c), inject: [INBOUND_SFTP_CONNECTION] }
```
inbound 一份 client、outbound 一份 client → cron 的 connect/disconnect 不再砍掉 result 上傳。
- **為什麼**：同 pod 內零死鎖、不必拆 pod / 不必共用 Redis；是 connection pool 的乾淨子集。

### Phase 2a — order-fetch 同一台 host 重用一條連線（PR #198）
把資料夾按 `host:port:username` **分組**，每組連一次、組內重用、組末關：
```
groupFoldersByHost()  →  processHostGroup()(一組 connect 一次)  →  processFolderOnConnection()(不 connect/disconnect)
```
172 連線/tick → ~1/host（實測 198 資料夾 → 25 條）。
- **為什麼是「重用」不是「並發連線池」**：對同一 vendor 開並發連線只會更快撞 per-IP 上限；瓶頸是連線數不是頻寬，所以正解是「少開連線」。
- 保留單資料夾 hang 防護：folder 逾時可能弄壞連線 → 砍掉並重連後續；重連失敗則該 host 剩餘延到下個 tick（靠 `SftpFileService.ensureConnected` 自動補連線）。

### Phase 2b — outbound result 上傳序列化（PR #201）
Phase 1 拆了 inbound/outbound，但**所有 result 上傳彼此仍共用 outbound client**。手動補送 overlap 自動 kafka pipeline（或多批同時）時，一筆上傳完 `disconnect()` 砍掉另一筆正在 `put()` 的 socket → 檔案上了但 gRPC 不回（prod sample 2566061）。
用 `SftpService` 的 **promise-chain** 把每次上傳串成不重疊 critical section：
```ts
private uploadChain = Promise.resolve();
private runSerialized(task) {
  const r = this.uploadChain.then(task, task);   // 等前一筆 settle 再跑
  this.uploadChain = r.then(()=>{}, ()=>{});      // 吞結果，單筆失敗不卡死整條鏈
  return r;
}
uploadHL7File(...) { return this.runSerialized(() => this.uploadHL7FileImpl(...)); }
```
- **為什麼用 chain 不用 mutex**：避開上述死鎖；每段保留自己的 `finally disconnect`；throughput 無損（vendor 本就喜歡一次一條連線）。

---

## Impact（影響）

| 指標 | 改前 | 改後（Phase 1+2a 線上實測） |
|---|---|---|
| `Unexpected end event` | ~6000 / 天 | **0** |
| SFTP 連線數 / cron tick | ~172 | **25**（每 host 一條） |
| order-fetch（inbound） | 被連線風暴拖死 | 198/198 資料夾每 15 分鐘掃完、檔案持續進 |
| result 上傳（outbound） | 卡死 / gRPC 不回 | 並發互不砍、上傳 success（Phase 2b 待 deploy 後最終驗證） |

- 確認 vendor（MDHQ）為 per-IP 連線上限：把連線數壓低後 throttle 歸零。
- 病人/provider 影響：result 報告恢復穩定遞送；消除「檔案已上傳但系統標失敗」的假失敗與重複上傳。

---

## 驗證（Verification）
- 單元測試：`src/modules/sftp` 4 suites（含新增 `sftp-inbound-isolation.spec`、`sftp.service.spec` 序列化測試：`maxActive===1`、connect/disconnect 不重疊、失敗不卡 chain）；`hl7-order-fetch.service.spec` 新增同 host→1 connect / 多 host→各 1 / no-creds skip。
- 線上（peer-observable）：deploy 後在 prod pod 直接觀測連線數、`Unexpected end event` 計數、order-fetch tick 完成、result 上傳成功、result+order 並發互不砍（抓到 9:00:58 cron 與 25s result 上傳重疊、上傳仍成功的實證）。

---

## 未來工作（Future）
1. **outbound per-host connection pool**：把「單一共用 client + 全域序列化」升級為「per-host 連線池 + bounded concurrency」→ **不同 vendor 之間可平行上傳**、同 host 仍受限。這是支援未來 parallel batch upload 的前提（同 host 平行會重蹈 per-IP throttle，不可行）。
2. 把 scheduled-reports / SFTP 測試端點等仍直接用 `SftpConnectionService` 的 outbound 路徑也納入序列化/池化。
3. 評估 `SFTP_UPLOAD_OP_TIMEOUT_MS`（現 10 分鐘）對大檔/慢 tenant 的 head-of-line 影響。
4. （獨立）`ResultStatusMapperService` 的 `OUT_OF_RESULT_NORMAL` enum 漂移 → TNP，屬 result 渲染問題，需另開 ticket 補 `OUT_OF_RESULT_*` 對應（需權威臨床值）。

---

## 技術關鍵字（供延伸學習）
Dependency Injection / IoC container、NestJS custom providers（useClass/useFactory）、provider token、injection scope；SSH/SFTP（channel、`SFTP_FXP_STATUS` ACK、half-open connection、keepalive、NAT idle timeout）；connection pool、semaphore / mutex、bounded concurrency、backpressure、head-of-line blocking；per-IP rate limiting / throttling（Bitvise WinSSHD）；idempotent upload、exponential backoff + jitter、post-timeout verification（`stat()`）。
