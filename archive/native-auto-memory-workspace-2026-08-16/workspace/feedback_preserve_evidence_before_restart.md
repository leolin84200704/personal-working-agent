---
name: preserve-evidence-before-restart
description: Hang/stuck pod 任何 destructive op (rollout restart / pod delete) 前必先 dump log + describe，否則 root cause 證據隨 pod GC 永久遺失
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 904372bb-59eb-4895-ba9d-b023a08378ae
---

**Rule**：對 hang / stuck pod 跑 `kubectl rollout restart` / `kubectl delete pod` 前，**先**：
```bash
kubectl logs <pod> -c <container> --since=24h > /tmp/preserve_<pod>.log
kubectl logs <pod> -c <container> --since=24h --previous > /tmp/preserve_<pod>_prev.log 2>/dev/null
kubectl describe pod <pod> > /tmp/preserve_<pod>_desc.txt
```
然後再 restart。

**Why**：INCIDENT-20260528 — V2 fetch lock-leak hang 19h，Leo 授權「(1) restart + (2) code fix」、我直接 `kubectl rollout restart`。舊 pod `6cc4674b87-ccgbf` 進 Terminating → 幾分鐘後 GC → `kubectl logs` 找不到 pod → `/var/log/pods/<old-pod>/` 對應 log file 也被清。「**哪個 folder 是 5/27 真正卡住的元凶**」這個關鍵證據永遠拿不回來。後來 21:45 tick 看到的 id=260 是 transient (22:00 tick 同 folder 通過)，跟原始 hang 不一定是同一個 folder。

**How to apply**：
- 任何「pod 卡死、考慮 restart」的情境都套這 SOP
- 即使 user 授權 restart、也先存證再執行（一兩秒成本、換永久 evidence）
- 大量 log 用 prod `/tmp` 寫檔 + `scp leo@192.168.60.5:/tmp/X.log .` 拉回本機，比 stdout 通道穩 (INCIDENT-20260518 同類教訓)
- restart 是「reversible 但會洗掉現場」的中間 risk 動作 — 不像 `rm -rf` 那麼明顯需要 confirm、但對 debug 的破壞性等同

關聯：[[reference_appserver04_ssh]]、[[INCIDENT-20260528]]。
