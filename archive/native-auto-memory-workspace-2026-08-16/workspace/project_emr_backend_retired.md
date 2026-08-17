---
name: project_emr_backend_retired
description: Java EMR-Backend fully retired 2026-06-10; all EMR orders now go through lis-backend-emr-v2
metadata: 
  node_type: memory
  type: project
  originSessionId: c10e94a6-3fcc-4829-91dd-0bcd398ff12a
---

Per Leo (2026-06-10): the Java **EMR-Backend** repo is **completely out of use** — all EMR-originated orders now flow through **lis-backend-emr-v2** (bestDeal / order / charging included). To change EMR order behavior, edit emr-v2 only; do NOT touch EMR-Backend.

This supersedes the older note that "only VP-16463 batch-cutover clients route through emr-v2; others still hit Java EMR-Backend" — that is no longer true.

Deploy reality (same date): live prod emr-v2 still runs **on-prem (192.168.60.x)**, NOT on AKS (cloud migration incomplete — AKS has the configmaps but no emr-v2 pod). The files `lis-emr-v2-config.yaml` (staging) and `lis-emr-v2-config-prod.yaml` (prod) are **gitignored local ConfigMap copies** that Leo applies via `kubectl apply` himself — editing them is the way to change prod env, and there is no PR/commit for them.

Related: [[project_emr_cloud_migration.md]]
