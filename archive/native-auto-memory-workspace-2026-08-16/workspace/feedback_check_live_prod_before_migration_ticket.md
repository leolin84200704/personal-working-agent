---
name: feedback-check-live-prod-before-migration-ticket
description: "For migration/cutover tickets, read live prod runtime state before assuming the work is undone — Jira status lies"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c6896c0c-5d36-45ba-89ad-96fde85c51dc
---

遷移／cutover 類 ticket（repoint endpoint、改 ConfigMap、切 service）開工前，先讀 **live prod runtime state**（kubectl get configmap、exec pod env），不要相信 Jira 狀態或 repo 快照。

**Why:** VP-16784/85/86/87（transv2 4 個 RPC on-prem→cloud）四張都還在 "Dev To Do"、repo 的 `prod-env.yml` 只含 1 個 key、`.env` 還是 on-prem，但 **live `lis-transv2-config` ConfigMap 早已 4 個 RPC 全指 cloud、無 on-prem 殘留**。若照 ticket 字面去「改 ConfigMap」會是 no-op 還白白 rollout restart 3 個 prod pod。repo yaml 是局部快照，真 source of truth 在 Azure AKS live ConfigMap（同 [[feedback-config-yaml-coupling-with-code]] 的 source-of-truth 模式）。

**How to apply:** 接到 migration ticket → 先 `kubectl get configmap <name> -n <ns> -o yaml` + `kubectl exec <pod> -- env | grep <VAR>` 確認跑著的 pod 實際值 → 若已是目標值就別動，改去驗證（見下）。驗證 cloud `.svc.cluster.local`（只 AKS 內可解析）用同 image 的 serving pod 跑 node `@grpc/grpc-js`+repo proto 做 cloud vs on-prem 唯讀逐欄位 diff；read-only child process 不會 crash container。相關 [[feedback-verified-means-live-not-mock]]、[[feedback-end-to-end-equivalence]]。
