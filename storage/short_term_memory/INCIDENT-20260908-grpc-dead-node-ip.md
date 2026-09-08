---
id: INCIDENT-20260908-grpc-dead-node-ip
title: emr-v2 result generation outage — every GRPC_*_CLOUD_HOST / GRPC_V2_*_HOST pointed at a
  recycled AKS node IP (10.224.0.199); repointed to 10.224.0.10, pods restarted, 58 pushes re-driven
category: technical
status: completed
created: 2026-09-08
updated: 2026-09-08
tags:
- incident
- emr-v2
- grpc
- aks
- node-ip
- configmap
- result-generation
- coresamples-v2
related:
- VP-18055
- VP-18095
- INCIDENT-20260518
- INCIDENT-20260817-onprem-stale-deploy
---

# INCIDENT 2026-09-08 — result pushes failing: gRPC targets pointed at a dead AKS node IP

## Detection
- Found while live-checking the PR #401 deploy (17:33Z): all 22 result pushes created after the deploy were
  GENERATION_ERROR with `14 UNAVAILABLE ... connect ETIMEDOUT 10.224.0.199:32100`. NOT caused by #401:
  rtr errors on 10.224.0.199 start 2026-09-06 04:48Z, 6/6 failed 09-07 21h, 26/69 failed 09-07 23h,
  100% from 09-08 17h. Both prod pods (AKS + on-prem) affected.

## Root cause
- `10.224.0.199` was an AKS node IP used as the NodePort entry for three services: lis-core v1 gRPC
  (`lis-core-grpc-service` 30276), lis-test-connect (30600), coresamples-v2 (`lis-coresamples-v2-service-nodeport`
  32100 → 8084). The node no longer exists (current node hostIPs: 10.224.0.10 systemonly, 10.224.2.184 /
  10.224.0.244 agentpool, 10.224.1.215 / .1.115 / .0.145 / .1.84 userpool; az finds no NIC with .0.199).
- The IP is hard-coded in 8 keys (`GRPC_{CUSTOMER,PATIENT,SAMPLE,TEST_RESULT,REFERENCE_RANGE}_CLOUD_HOST`,
  `GRPC_V2_{CUSTOMER,PATIENT,SAMPLE}_HOST`) in ALL SIX emr-v2 ConfigMaps (AKS ns emr-v2 ×2, AKS ns default ×2 =
  the copies Jenkins fetches and applies to both clusters on every deploy, on-prem ns default ×2), plus the code
  defaults in `src/config/grpc.config.ts` and repo yaml (`k8s/base/configmap.yaml`, `azure-lis-emr-v2-configmap.template.yaml`).
- v2 clients have no fallback; v1 "on-prem fallback" 192.168.60.6:30276 is dead (nc CLOSED, as recorded on 08-20).
- AKS prod live copy already had 2 keys on `lis-coresamples-v2-service.coresamplesv2.svc.cluster.local` (cluster DNS —
  works on AKS only, not on-prem).

## Fix (Leo "done" = go, 19:06Z)
- Backups of all 6 ConfigMaps: scratchpad `cm-backup-20260908T1801Z/` (session-local; note the
  `last-applied-configuration` annotation still carries the old IP and, incidentally, plaintext secrets such as
  ADOBE_CLIENT_SECRET — ConfigMap hygiene issue, pre-existing).
- `kubectl patch --type merge` on each ConfigMap for exactly the keys whose value == 10.224.0.199 → `10.224.0.10`
  (systemonly pool node; all 3 ports OPEN from on-prem 60.5 via nc; every current node serves the NodePorts).
  Readback: 8/8 keys per ConfigMap, 0 remaining except the annotation.
- Restarts: on-prem prod `rollout restart` (new pod 5968864f85-2md9w 19:07Z); AKS prod by `delete pod` (my AAD
  identity can delete pods but NOT patch deployments/exec) → 5d4784d79b-ft85q 19:08Z; staging both clusters.
  Startup logs on both prod pods: `v2 ... gRPC client created: 10.224.0.10:32100`.
- Re-drive: GenerateResultHl7 via 60.6:31317 UPDATES the existing rtr row (probe 2485882: same created_at,
  now GENERATED/TRANSMITTED, processing pod = new on-prem pod). 37 PERMANENT FAILURE samples re-driven
  (redrive_perm.txt, 10s pacing); 21 still inside auto-retry left to the pipeline, to be checked afterwards.

## Access gotchas learned today
- AKS kubectl: cluster has local accounts disabled; kubeconfig needs Azure `kubelogin` (`az aks install-cli
  --kubelogin-install-location ~/bin/kubelogin`, `kubelogin convert-kubeconfig -l azurecli`; symlinked into
  /opt/homebrew/bin). `brew install kubelogin` is the wrong project (int128 OIDC). My identity: get/list, patch
  configmaps, delete pods = yes; patch deployments, pods/exec, list nodes = no. Node IPs readable via
  `kubectl get pods -A -o custom-columns=NODE:.spec.nodeName,HOSTIP:.status.hostIP`.

## Follow-ups (not done)
- Node IPs are not stable service addresses; the next node image upgrade repeats this. coresamples-v2 already has
  an internal LB (`coresamplesv2-loadbalancer` 10.224.1.113:80→8084, reachable from on-prem); lis-core-grpc and
  lis-test-connect have none. Proposal: internal LBs (or consul DNS `lis-core-grpc.service.consul`, which on-prem
  60.5 cannot resolve today) + ConfigMap/code defaults on those addresses. Needs a ticket + PR (grpc.config.ts
  defaults, k8s yaml, template).
- No alert fired for a 100% result-generation failure lasting hours: result_fail DailyJob only reports next morning.
  A Sentry alert on GENERATION_ERROR rate (or on `14 UNAVAILABLE`) is the gap.
