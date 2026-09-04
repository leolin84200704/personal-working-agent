---
id: INCIDENT-20260817-onprem-deploy-freeze
title: 'on-prem emr-v2 froze at 2026-08-04 for 13 days: a fatal Kafka guard on a pod
  with no Azure identity, hidden by maxUnavailable 0'
status: resolved
category: technical
created: 2026-08-17
updated: '2026-08-19'
tags:
- incident
- deploy-skew
- kafka
- key-vault
- workload-identity
- on-prem
- vp-17595
- vp-17559
- vp-17715
summary: VP-17559 moved the Event Hub SAS to Key Vault (2026-07-30); the on-prem pod
  has no Azure identity so its vault read always failed and it silently fell back
  to the on-prem brokers. VP-17595 (2026-08-04) removed that fallback on the wrong
  premise that those brokers were decommissioned — they were not; the ones decommissioned
  that day were VP-17593's notification brokers. Every on-prem pod built after 19:41Z
  then died in onModuleInit; maxUnavailable 0 kept the 08-04 pod serving, so ~45 main
  merges never rolled out and nobody noticed for 13 days. Surfaced 08-17 as two failed
  MDHQ orders when VP-17715's PER_REPORT_GROUP enum reached a Prisma client older
  than itself. Fixed by putting the SAS in the AKS default-ns ConfigMap (the copy
  Jenkins syncs on-prem) — on-prem now genuinely consumes the Event Hub. SP + Key
  Vault remains the destination, blocked on an Azure admin.
links:
- INCIDENT-20260518
- INCIDENT-20260817-onprem-stale-deploy
- QH-1130
- QH-1159
- QH-1591
- QH-862
- QH-918
- QH-919
- VP-15460
- VP-16168
- VP-16169
- VP-16172
- VP-16391
- VP-16499
- VP-16513
- VP-16520
- VP-16521
- VP-16629
- VP-16689
- VP-16785
- VP-16786
- VP-16787
- VP-16859
- VP-16921
- VP-16968
- VP-17065
- VP-17217
- VP-17222
- VP-17312
- VP-17422
- VP-17577
- VP-17714
- VP-17753
- VP-17754
- VP-17825
- VP-17870
- VP-18048
- VP-9299
- business-model
- failures
- repo-catalog
- repos
score: 0.3548
---

# INCIDENT 2026-08-17 — on-prem emr-v2 deploy freeze

## Timeline (all verified against the live systems, not reconstructed from tickets)

| When | What |
|---|---|
| 07-29 | VP-17561 cloud Kafka cutover. Verified **inside AKS only**. |
| 07-30 | VP-17559 moves the SAS from ConfigMap to Key Vault; the ConfigMap key is emptied. On-prem loses its cloud credential and silently falls back to the on-prem brokers (a WARN). |
| 08-04 19:16Z | Last on-prem pod that could start: `777c956c9b-xs52b`. |
| 08-04 19:41Z | VP-17595 removes the on-prem fallback, makes a cloud-connect failure fatal. |
| 08-05 → 08-17 | Every main build pushes an image and restarts the deployment; every new pod throws in `onModuleInit` and CrashLoopBackOffs. `maxUnavailable: 0` keeps the 08-04 pod serving. Deployment revision climbs to 234 with `ProgressDeadlineExceeded`. Jenkins Slacks FAILURE each time. |
| 08-17 20:15Z | hl7_file_input 6868/6869 (cust 4953 Resilience Code, MDHQ) fail: `Value 'PER_REPORT_GROUP' not found in enum 'ResultPushLevel'` — VP-17715's value, live in the DB since 08-14, hitting a Prisma client from 08-04. |
| 08-17 23:22Z | Fixed: SAS into the AKS `default`-ns ConfigMap, `AZURE_*` removed from the manifest, rollout completes to revision 239. |

## Root cause, in layers

1. **A premise inherited instead of measured.** VP-17595's commit says the brokers
   192.168.60.9/10/11:9095 "were decommissioned on 2026-08-04". The brokers decommissioned
   that day were VP-17593's *notification* brokers — different cluster, same three hosts, same
   date. One TCP connect, or one look at the running pod's socket table, would have refuted it.
   That check took 30 seconds on 08-17.
2. **"No behavior change" measured on the convenient environment.** The same commit claims no
   behavior change "while the cloud path is healthy (live since VP-17561)". The cloud path was
   healthy *on AKS*. On-prem had never once been on it.
3. **A fallback was removed while something was standing on it.** Between 07-30 and 08-04 the
   system was already broken and self-healed into a degraded mode that logged at WARN. The
   fail-loud instinct was right; applying it to a degraded state nobody had observed was not.
4. **Failure was made fatal at the wrong altitude.** The Kafka consumer's connect failure kills
   a pod that also runs order intake for 197 of 198 SFTP folders. One subsystem's credential
   problem became a total deploy freeze.
5. **`maxUnavailable: 0` makes a failed rollout indistinguishable from a healthy service** to
   anyone looking at pods or endpoints.

## Why it stayed invisible for 13 days

- The alert existed and fired ~45 times (Jenkins `post { failure }` → `slackSend` to `lis-bot`
  and `portal-emr-bot`). Nobody read a red build as "the deploy did not happen".
- LTM already said `push 即 deploy` for this repo, which is true for AKS and false for on-prem.
- On-prem is not in the local kubeconfig, so it was *inferred* rather than checked — and the
  workaround I had written down (`hl7_file_input.last_update_pod_name`) was a substitute for
  access I never asked for. **The access existed the whole time** (`ssh leo@192.168.60.5`).
- Staging cannot catch this class at all: on-prem staging runs `ENABLE_KAFKA_CONSUMER=false`,
  so the crash path never executes there.

## Why it hurt when it finally surfaced

`hl7-order.processor.resolveIntegration` selected every column of `ehr_integrations` for what
its own comment calls "a non-failing observability log". An enum on a column the order path
never reads threw out of `processFromFile` and killed the order. The authoritative readers
(`customer-detail-fetcher`, `shortcut.service`) already project and were unaffected.

## Fixes shipped

- PR #369 → merged: order-path projection + try/catch (`ec231d2`), plus a manifest commit that
  should not have been in it.
- PR #371: reverts that manifest (it references a Secret that does not exist, and the 23:08Z
  main build applied it and refroze on-prem until it was rolled back by hand at 23:22Z); fixes
  three documents that described AKS as if it were both environments.
- Personal repo PR #31: daily deploy-skew check across all four targets, with a `--self-test`
  that replays this incident's cluster state and asserts both signals fire.

## Verified end state (2026-08-17 23:22Z+)

- on-prem pod `7b5fc4df44-ggmgh` 2/2 Running, revision 239, current image.
- `✅ Kafka consumer running on cloud cluster, topic=general-sample-events`; ESTABLISHED to
  `20.150.246.149:9093`, and the three `192.168.60.x:9095` sockets are gone.
- SAS present in AKS `default` + `emr-v2` and on-prem ConfigMaps, 144 chars, matching sha256
  prefix, all three backed up.

## Open

1. **SP + Key Vault** — blocked on an Azure admin. Assigning `Key Vault Secrets User` on
   `vibrant-app-secret` needs Owner / User Access Administrator; Leo's only RBAC is AKS
   Contributor. Every AKS service uses workload identity (`emr-v2/identity-provider` →
   managed identity `ae63b423` `Portal-Order-Service`), and a managed identity has no client
   secret to borrow. `docs/VP-17561-KAFKA-CLOUD-CUTOVER.md` names **Tianhao Wang** as the
   person who created that federated credential.
2. **Rotation hazard while the ConfigMap holds the SAS**: rotating it in Key Vault now silently
   diverges from both ConfigMaps, and the code prefers the ConfigMap — so AKS would go stale too.
3. Whether a Kafka connect failure should be fatal on a pod that also runs order intake.
4. hl7_file_input 6868/6869 re-parse confirmation (retry_num bumped 0→3 at 23:23:56Z).

> **同一事故的另一面**：`INCIDENT-20260817-onprem-stale-deploy` — 症狀面與補救（MDHQ 兩份報告、cloud pod 重推、drift scope）。兩份刻意不合併：一份記症狀與補救，一份記機制。

### [2026-08-19] RESOLVED（dream 判定）

- 機制修復已 live 驗證：on-prem pod 真的在消費 Event Hub（SAS 進 Jenkins-sync ConfigMap），
  且 2026-08-18 起與 AKS 同步重啟（LIS-7690 uptime parity probe）。
- **Open item 4 已確認**：hl7_file_input 6868/6869 的 re-parse — 2026-08-19 daily triage
  在 72h 窗（涵蓋 08-17）掃到 27 筆全部 parse 成功、`parse_finished=0` 為 0 筆，
  兩單已恢復。
- Open item 1（SP + Key Vault）= **VP-17756**（Leo:「未來會做」）；item 2 rotation hazard
  跟著 VP-17756；item 3 是設計問題，留給該 ticket。本檔標 resolved。
