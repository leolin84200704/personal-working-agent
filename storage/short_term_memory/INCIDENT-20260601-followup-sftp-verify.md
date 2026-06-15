---
id: INCIDENT-20260601-followup-sftp-verify
type: stm
category: technical
status: pending
score: 0.1
base_weight: 0.9
created: 2026-06-01
updated: 2026-06-01
links:
- INCIDENT-20260601-sftp-hang
- INCIDENT-20260604
tags:
- sftp
- false-negative
- post-timeout-verify
- leo-deferred
summary: 'A+B follow-up: keep SFTP_UPLOAD_OP_TIMEOUT_MS=10min, add stat() verify after
  timeout to fix false-negative ERROR records (e.g. sample 2560935 9MB Athena upload
  succeeded but DB marked ERROR)'
---







# Follow-up: SFTP Upload Post-Timeout Verify

> Created: 2026-06-01
> Status: **deferred by Leo, 等等再做**

## What

INCIDENT-20260601 1h e2e test 暴露：`SFTP_UPLOAD_OP_TIMEOUT_MS=10min` fire 後，**檔案可能實際已在 vendor folder 但 DB 標 TRANSMISSION_ERROR**。原因是 ssh2-sftp-client.put() 在等 SFTP_FXP_STATUS ACK，data 早已 TCP-flushed 但 vendor server 慢 ACK，10min cap 比 ACK 早 fire。

具體案例：sample 2560935 9MB Athena upload 9:59:50 開始，22:09:50 timeout，但 Leo 在 Athena `/inboundintoathena/` 看到檔案實際存在。

## Decision (Leo 2026-06-01)

走 **A+B 但維持 timeout 10min**：
- A: NOT raising timeout（保留 10min worker pin cap）
- B: 加 post-timeout `client.stat(remotePath)` verify
  - File exists in vendor → mark TRANSMITTED（不是 ERROR）
  - File not exists → mark TRANSMISSION_ERROR（如現狀）

## Why A+B 不只 B

僅做 B 沒解 timeout 後 worker 已經卡 10min 的成本，但 10min 是 Leo 接受的範圍。

## Why 不加大 timeout（不走 pure A）

加大會讓 worker 卡更久（concurrency=1，所有後續 sample 等待）。10min 是 throughput + 安全的折衷。

## Concern (Leo): MDHQ 額外 request 風險

Leo 擔心 stat() 每次 timeout 都打 = 多 request，過去 MDHQ IP-based throttle 過。

評估：
- stat() ≈ 100 bytes vs upload ≈ MB 級。輕量極多
- 1h test 觀察 30 個 timeout = 30 個 stat / hour，很低速率
- Vendor anti-DOS 不會因 stat 觸發
- BUT 若 MDHQ throttle 邏輯包含 "total connection count regardless of payload size"，stat 仍可能踩到

緩解：
- 預設 stat 走主要 client（不開新連線）使用已建立的 SFTP session
- 若需另開連線，加 jitter/delay (e.g., 1-3s) 在 stat 前
- 加 metric 觀察 stat 失敗率，便於後續調整
- 仍提供 env kill switch `SFTP_POST_TIMEOUT_VERIFY_ENABLED=false` 預防 vendor 反應不好可快速 disable

## Implementation sketch

```typescript
// sftp-file.service.ts uploadFile
try {
  await this.withTimeout(client.put(localPath, remotePath), uploadTimeout, ...);
} catch (err: any) {
  if (err.isTimeout && process.env.SFTP_POST_TIMEOUT_VERIFY_ENABLED !== 'false') {
    try {
      // Same client (session likely still alive), one stat call
      const stat = await this.withTimeout(
        client.stat(remotePath),
        parseInt(process.env.SFTP_VERIFY_OP_TIMEOUT_MS || '10000', 10),
        `stat verify timed out: ${remotePath}`,
      );
      // Compare size to expected
      const localStats = fs.statSync(localPath);
      if (stat.size === localStats.size) {
        this.logger.warn(`[upload-timeout-but-verified] ${remotePath} exists with matching size; treating as SUCCESS`);
        return { success: true, localPath, remotePath, size: localStats.size, uploadTime: new Date(), recoveredFromTimeout: true };
      }
    } catch (_) {
      // verify failed, fall through to throw original timeout
    }
  }
  throw err;
}
```

## Yaml needed

新 env vars 兩份 yaml 都加（per [[config-yaml-coupling-with-code]]）：
- `SFTP_POST_TIMEOUT_VERIFY_ENABLED: "true"`（kill switch）
- `SFTP_VERIFY_OP_TIMEOUT_MS: "10000"`

## Estimated effort

- Code: 20 行 + spec test
- Yaml: 2 行 × 2 files
- Total: <1 hour

## Trigger condition to revisit

當下次 prod incident 又出現「DB ERROR 但 vendor 收到 file」case，且累積影響 > 5 個 sample / week，就 priorities 起來做。
