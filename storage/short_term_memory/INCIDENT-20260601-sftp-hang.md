---
id: INCIDENT-20260601-sftp-hang
type: stm
category: technical
status: active
score: 0.2658
base_weight: 0.9
created: 2026-06-01
updated: 2026-06-01
links:
- INCIDENT-20260518
- INCIDENT-20260528
- INCIDENT-20260529
- INCIDENT-20260601-followup-sftp-verify
- INCIDENT-20260604
- VP-15460
- VP-16154
- VP-16165
- VP-16232
- VP-16337
- VP-16391
- VP-16410
- VP-16499
- VP-16521
- VP-16859
- failures
- repos
tags:
- sftp
- hang
- singleton
- deadlock
- mdhq
- ssh2-sftp-client
summary: 'lis-emr-v2 pod recurring hang: SftpConnectionService singleton''s safeDisconnect
  awaits client.end() with no timeout, blocking all callers'
---



















# INCIDENT-20260601 — SFTP Singleton Deadlock Hang

> Created: 2026-06-01 17:20 UTC
> Status: active — workaround applied (rollout restart); P0 fix pending

---

## Ticket Analysis

**Symptom**: lis-emr-v2-deployment-prod pod stops processing BullMQ result-generation jobs after running for some time. Last visible log line is always `[Hl7OrderFetchService] HL7 fetch complete: 0 file(s) enqueued from 196/196 folder(s)`. Pod's network is fine, container is alive (CPU 77m, mem 219Mi), but produces 0 log lines for 6-13 min. Self-heals eventually OR requires pod rollout restart.

**Impact**:
- 5/30~6/1: 157-sample batch retry stuck at 116/157 succeeded; 10 PENDING jobs in BullMQ permanently stuck after every recurrence.
- All Hl7 result push (outbound SFTP) blocked during hang.
- v1 EMR scaled to 0 (5/31) helped reduce frequency but didn't eliminate.

---

## Root Cause

### 🔴 Primary defect — Smoking gun

`src/modules/sftp/services/sftp-connection.service.ts:238-256`

```typescript
private async safeDisconnect() {
  if (this.client) {
    try {
      this.logger.log('Disconnecting from SFTP server');
      await this.client.end();   // ⚠️ NO TIMEOUT — hangs forever if server doesn't ACK SSH_MSG_DISCONNECT
    } catch (error: any) { ... }
    finally {
      this.client = null;          // never reached because await blocks
      this.isConnected = false;
    }
  }
}
```

`client.end()` (ssh2-sftp-client) sends SSH_MSG_DISCONNECT and awaits ack. Vendors that misbehave (e.g., MDHQ Bitvise WinSSHD throttling, half-open sessions) accept TCP + send banner but drop the SSH session mid-channel → ack never comes → await hangs forever → `finally` block never executes → `this.client` stays referenced → next caller's `safeDisconnect()` queues behind it.

### Why this becomes a deadlock

1. **`SftpConnectionService` is a NestJS singleton.** One `client` field shared by:
   - `Hl7OrderFetchService` (cron every 15min, iterates 196+ vendor folders)
   - `ResultGenerationProcessor` (BullMQ worker, concurrency=3)
   - All gRPC `GenerateBatchResultsHl7` callers

2. **`connect()` calls `safeDisconnect()` first** (line 46) to clear stale state. So even fresh `connect()` calls get stuck.

3. **Once one caller is stuck on hung `client.end()`**, every subsequent caller calling `ensureConnected() → reconnect() → disconnect() → safeDisconnect()` (line 266-274) also blocks on the same `await`.

4. **Result**: 3 result-gen workers + cron next tick + R8/R9 grpcurl batches all freeze.

### Why "self-heal" eventually happens

- `keepaliveInterval=10000ms, keepaliveCountMax=3` provides SSH-level keepalive (~30s) but only on healthy sessions, not on hung `client.end()`.
- OS-level TCP keepalive on Linux defaults to ~2 hours; `net.ipv4.tcp_keepalive_time=7200`. In practice, hangs observed clear after 6-13 min — likely OS sending RST after several timeouts during the broken socket I/O attempts, or BullMQ's `JOB_HARD_TIMEOUT_MS=600s` firing in worker and aborting the await (though Promise.race won't actually kill the socket op, the worker's job slot is freed).

### Why MDHQ was the trigger most often

MDHQ vendor SSH (Bitvise WinSSHD 6.44):
- accepts TCP
- sends banner `SSH-2.0-5.36 FlowSsh`
- then drops session at auth/channel-setup phase when throttled
- never responds to `SSH_MSG_DISCONNECT` (because session is half-closed from server side)

Combined with v1 EMR also hammering MDHQ for inbound → IP rate-limit triggered → vast majority of MDHQ sessions land in this half-broken state.

---

## Approaches Considered

### Approach A — Patch `safeDisconnect()` with timeout (P0, lowest risk)
- ~10 lines, single file
- Clear ref immediately + `Promise.race` with 5s timeout + force-destroy underlying socket

### Approach B — Replace singleton with per-call instance / pool (medium risk)
- NestJS `Scope.TRANSIENT` or hand-rolled pool keyed by `host:port`
- Larger refactor; each operation pays SSH handshake cost
- Eliminates cross-vendor contention

### Approach C — Wrap every file op with timeout
- `uploadFile()`, `listFiles()`, `downloadFile()` already missing per-op timeout (only `createDirectory()` has it via existing `withTimeout()` helper)
- Defense in depth

### Approach D — k8s liveness probe (independent)
- Detect hangs externally and auto-restart
- Requires `/health/liveness` endpoint with event-loop heartbeat check

---

## Decisions Made

- **Immediate workaround**: `kubectl rollout restart deployment lis-emr-v2-deployment-prod` (executed 2026-06-01 ~10:16 PDT)
- **Next step (P0)**: Patch `safeDisconnect()` per Approach A. Leo to confirm.

---

## Code Changes

(pending)

Proposed patch:

```typescript
private async safeDisconnect() {
  if (!this.client) return;
  const c = this.client;
  // Clear ref immediately so subsequent callers don't queue behind us
  this.client = null;
  this.isConnected = false;
  try {
    await Promise.race([
      c.end(),
      new Promise((_, rej) => setTimeout(() => rej(new Error('disconnect_timeout')), 5000)),
    ]);
  } catch (err: any) {
    this.logger.warn(`safeDisconnect timeout/err: ${err.message}, force-destroying socket`);
    try { (c as any)?.client?.end?.(); } catch {}
    try { (c as any)?.client?._sock?.destroy?.(); } catch {}
  }
}
```

---

## Test Results

(pending — verify with stress test where MDHQ drops connection mid-session)

---

## User Feedback

- Leo (2026-06-01): "為什麼會這樣？找出root cause 然後告訴我怎麼修" → asked for root cause + fix
- Leo (2026-06-01): "ok, 請重啟，另外找出原因" → authorized rollout restart, asked to document cause

---

## Failures

- 5/30 INCIDENT-20260528: identified same symptom but only documented "Required pod rollout restart". Root cause was not traced into the singleton/await chain. Recurrence on 6/1 demanded deeper investigation.

---

## Retrospective

- **Pattern recognition**: similar hang symptom on 5/28 was treated as one-off and only mitigated by restart. The root cause analysis was deferred. Result: same hang recurred on 6/1, blocking the 157-sample retry effort.
- **Lesson**: when an operational symptom recurs, escalate to code-level root cause immediately rather than relying on workaround.

---

## Lessons Learned

1. **Any `await network.close()` in a Node.js singleton MUST have a timeout + force-destroy fallback.** Otherwise misbehaving peer locks the entire service.
2. **Singletons that wrap network handles** become single points of failure. Prefer per-caller instances or a pool with explicit acquire/release semantics.
3. **`finally` block does NOT run if the preceding `await` never resolves.** Always clear shared mutable state BEFORE the await, not in `finally`.
4. **k8s livenessProbe is the safety net** — without it, a process that hangs in user-space but keeps the TCP socket alive will never be restarted by k8s automatically.
