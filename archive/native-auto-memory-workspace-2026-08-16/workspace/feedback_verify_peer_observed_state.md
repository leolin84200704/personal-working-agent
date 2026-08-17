---
name: feedback-verify-peer-observed-state
description: "Network lifecycle / IPC / RPC fix 的 verify plan 必須包含 peer-observed state，不只我方 pod log。INCIDENT-20260604: 60601 patch 解了 pod hang 但留 MDHQ side leak 因為 retro 只驗自己端"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 37705de5-a5b9-4549-b1be-2b522e1b4b48
---

# 規則

修 network handle / IPC / 跨 service lifecycle 的 PR，**verify plan 必須有 peer-observed state axis**：

- 我方 side（pod metric / log / unit test）— 你的程式邏輯確實過了
- **peer side（vendor session count / netstat from peer / their reports / 反向觀察自己 pod 對 peer 的 socket state）** — 對方真的觀察到 lifecycle event

## How to apply

任何 lifecycle 修改（connect / disconnect / RPC close / queue release / lock release）：

1. 列出所有 external parties — 你 disconnect 後誰應該觀察到什麼？
2. 對每個 party 找 observability：
   - 直接 metric（vendor 提供 stale connection count、k8s service mesh metric）
   - 反向觀察（pod 內 `netstat -ntp` 看 to-peer connections over time、grep peer 的 stale session log）
   - 最差 case：deploy 後 24-48h ping vendor 確認 stale count 變化
3. Verify success criterion 寫成「peer-side observable 改變」not「my-side log 印對」

## Why（INCIDENT-20260601 → 20260604 連環事件）

INCIDENT-20260601 patch fallback 是 `client.end(); _sock.destroy();`。我方 pod 端 verify：
- pod 不再 hang ✓
- worker 不再卡 ✓
- log 印「force-destroying socket」warning，認為「OK 沒事」

但實際上 `socket.destroy()` 不保證送 TCP FIN，`client.end()` async 沒等 SSH_MSG_DISCONNECT 寫進 socket。從 MDHQ Bitvise 視角看：
- TCP 還在 / 還在 application-layer session table
- 沒收到 SSH_MSG_DISCONNECT → 標 "abandoned"
- 等 idle reaper（幾小時）才清

3 天後 MDHQ 報「20 stale sessions/day from 45.24.217.146」。

如果當時 60601 retro 順手做：
- `kubectl exec ... netstat | grep MDHQ host | grep ESTABLISHED` over 2h
- 或問 MDHQ「stale count 還高嗎」
- 就會發現 fix 沒完。

## 同類前科

- [[verified-means-live-not-mock]]：別把 mock unit test 講成「線上驗證」
- [[feedback_test_before_push]]：unit test 涵蓋新 logic 分支
- 共通：「我這邊看起來 OK」≠「整個系統 OK」。修跨系統 lifecycle bug 必須驗跨系統 state。
