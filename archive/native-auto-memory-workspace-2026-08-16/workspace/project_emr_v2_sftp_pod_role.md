---
name: project_emr_v2_sftp_pod_role
description: emr-v2 prod result-push hangs when order-fetch cron fires — shared SFTP singleton; POD_ROLE intake/pusher split built but never deployed (verified 2026-06-25)
metadata: 
  node_type: memory
  type: project
  originSessionId: 99dcff7b-017c-4aa9-b3ee-802733ba4be2
---

lis-backend-emr-v2 on-prem prod：result 上傳進行中、`Hl7OrderFetchService` `@Cron('0 */15 * * *')` 一觸發就把上傳卡死。根因：`SftpConnectionService` 是 NestJS singleton 共用 `this.client`，`connect()` 第一行無條件 `safeDisconnect()`（sftp-connection.service.ts:47-48）+ 無 mutex；order-fetch 逐 folder `connect()`（hl7-order-fetch.service.ts:269）→ 砍掉正在 `put()` 的 socket → 等不到 ACK 卡到 10min timeout / `getConnection: Unexpected end event`（單日 6000+）。是 INCIDENT-20260601 重現。

`config/pod-role.ts` 的 `POD_ROLE=intake|pusher` 分流就是為此而寫，但 **2026-06-25 查證：兩個 on-prem pod（`lis-emr-v2-deployment` app=lis-emr-v2、`lis-emr-v2-deployment-prod` app=lis-emr-v2-prod，均 appserver04 192.168.60.5 kubectl，default ns）spec 都沒設 POD_ROLE → 全 default `all` → 分流從沒生效**。**且不能直接設 env 分流**：兩 pod 都 `REDIS_HOST=localhost`（各自 redis sidecar，不共用），分流設計靠共用 Redis 當 intake→pusher result-gen job 橋樑 → 直接分流會斷自動結果路徑。→ **正解傾向 connection pool（keyed by host:port + acquire/release）讓 `all` 安全**，非 POD_ROLE 分流。

**2026-07-02 更新**：POD_ROLE 首次真的部署 — AKS Phase A prod pod（AKS ns `emr-v2`，`lis-emr-v2-deployment-prod`）設 `POD_ROLE=web`（fetch/pusher cron 全關，只服務 web/API），on-prem 兩 pod 仍 `all`。教訓（VP-17120 後續）：**6/23–7/2 的 AKS 測試 pod 沒設 POD_ROLE 也沒設 HL7_LOCAL_ROOT** → 跟 on-prem 雙 fetcher 搶 SFTP（redlock 在各自 redis sidecar 鎖不到對方）、檔案進 AKS pod ephemeral /tmp、pipeline 重建 pod 即蒸發；且兩邊 rescan 共踩 DB retry_num（file-missing 也 decrement）→ 卡單雙倍速耗盡。Phase B cutover 必須：共用/搬移 HL7Message_prod storage（AKS /EMR_storage 目前無此目錄，與 on-prem 不同份）、單邊 cron、rescan 也 gate 在 intake role。

prod result-gen Service：`lis-emr-v2-internal-prod` / `lis-emr-v2-nodeport-prod`（:5000 gRPC）→ app=lis-emr-v2-prod。手動 batch 走同步 gRPC `GenerateBatchResultsHl7`（inline、`isPusher` gate、序列化 169 筆會超 gRPC deadline 看似卡住）；自動結果走 kafka→queue。MDHQ host `34.199.194.51:2210` 一台有 ~172 sub-folder → 單 cron tick 對同 host 172 次 connect/disconnect。詳見 lis-code-agent knowledge/patterns.md。相關 [[reference_appserver04_ssh]] [[feedback_pursue_cleaner_design]]（驗 REDIS_HOST 才發現分流不可行）。
