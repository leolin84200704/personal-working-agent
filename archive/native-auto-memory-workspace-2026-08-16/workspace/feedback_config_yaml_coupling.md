---
name: config-yaml-coupling-with-code
description: IRON RULE — 任何新 process.env.X 都必須在同一次回應主動 update + 明說 lis-emr-v2-config*.yaml，不准等使用者問
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 799fca3a-9b4e-463a-ab2a-8ee00b54a461
---

# IRON RULE — 違反 = 不合理 ✋

**任何 commit / patch 引入新的 `process.env.X` 讀取**，這個 turn 必須：

1. **同步** 改 `lis-emr-v2-config.yaml`（staging）+ `lis-emr-v2-config-prod.yaml`（prod），把 key 明寫進去
2. **主動在回報裡明說「我也改了這兩份 YAML，部署時要 kubectl apply」** — 不准只 commit code 就交差
3. **不准等 Leo 問才補** — Leo 已經因為這件事重複糾正 ≥2 次（INCIDENT-2604156666 + INCIDENT-20260601）

## 觸發條件（凡是符合就要做）

`grep` 自己這次新加的 code，看是否含：
- `process.env.NEW_VAR_X` 
- `process.env.NEW_VAR_X || 'default'`
- `parseInt(process.env.NEW_VAR_X || 'N', 10)`
- 任何讀新 env key 的形式

只要有 **任何一個** 新 env key，就必須做上面 3 件事，包括 timeout / feature flag / host / port / 任何 default。

## Why（為什麼這條是 iron rule）

- ConfigMap 是 ops 看的 source of truth；code default 是隱式
- Jenkins 從 Azure AKS 拉 ConfigMap overwrite 本地檔（見 `azure-lis-emr-v2-deployment-prod.yaml` 註解），yaml drift 真實會發生
- Default 在 prod 是賭運氣：改 default 沒人察覺、新 env deploy 沒人補、prod/staging 漂移無法 audit
- Leo INCIDENT-2604156666 直接質問「為什麼不用設？這樣不就導致 code 完全沒用嗎」
- INCIDENT-20260601 我又重犯，pushed 3 commits 引入 9 個新 env key 都沒主動講，被 Leo 抓到

## How to apply（每次 commit 前的 checklist）

```
□ git diff 看是不是新加了 process.env.X
□ 改 lis-emr-v2-config-prod.yaml
□ 改 lis-emr-v2-config.yaml
□ 回報裡明確列出：「新增 env vars: X / Y / Z, 兩份 YAML 都改了, 部署時 kubectl apply」
□ 不只列在 commit message — 要在對話訊息裡主動講
```

## 範圍（涵蓋所有 env-driven config）

- 不只 GRPC — DATABASE_URL / KAFKA_* / API_BASE_URL / feature flag / timeout / concurrency 全部適用
- 包括 staging-only feature flag — 反正 prod yaml 也加 `=false` 明寫，避免之後忘了 toggle
- POD_ROLE 之類 routing key 同理

## 同類前科

- VP-16685（cloud-mirror）— code 加路徑、yaml 沒設
- INCIDENT-2604156666 revert — Leo 直接 review 抓出
- INCIDENT-20260601（2026-06-01）— 我引入 9 個新 env（SFTP_*_TIMEOUT_MS / RESULT_GEN_WORKER_CONCURRENCY / GRPC_V2_PATIENT_*_TIMEOUT_SEC），3 個 commits 都沒主動更新 YAML，等 Leo 問才補。**這是同類問題的第 3 次**。
