---
name: audit-callers-when-adding-fallback
description: 加 fallback infrastructure（cloud-with-onprem-fallback / retry wrapper）時必 audit 並 migrate 所有同類 v2-direct caller；revert 一個 v2 service 時必 audit 同 server 上其他 v2 服務的同類風險
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 37705de5-a5b9-4549-b1be-2b522e1b4b48
---

# 規則

兩個 trigger 必須各自配 audit + migration：

## Trigger 1: 加 fallback 基礎建設時

當在 `GrpcClientService` 之類 wrapper 加入 cloud-primary + on-prem fallback（如 `tryCloudThenOnPrem`、`Promise.race`、retry wrapper），**同 PR 必須**：

1. `grep` 所有 v2-direct caller（在我們的 case：`GrpcClientV2Service.someRpc`）
2. 列出哪些可以 migrate 到 v1 wrapper 享受 fallback
3. 同 PR 把 v1 wrapper 加上對應方法（v2 wrapper 有什麼、v1 wrapper 也要有對應的），並 migrate caller
4. **不准** 只 wire 已存在的 method 然後 commit message 寫 "for all methods including X" — 那是謊話，是這次 incident 的 gap 1 來源

## Trigger 2: revert 一個 v2 service 時

當某個 v2 RPC 在 prod 出問題（hang / error spike / data corruption）被 revert 回 v1（如 INCIDENT-2604156666 sample data revert），**同 PR 必須**：

1. grep `GrpcClientV2Service.<methodOnSameServer>` 列出同一個 v2 server (`coresamples_service` @ `10.224.0.199:32100`) 上所有 caller
2. **每一個** 都做 risk assessment：server 既然壞了一個 RPC，其他 RPC 也可能隨時壞
3. 如果有 v1 wrapper 可用 → 同 PR migrate
4. 如果 v1 沒有對應 method → 至少加 deadline + 加 TODO + 開 followup ticket
5. **不准** 假設「只有出事那個 RPC 有問題，其他繼續用」— 那是這次 incident 的 gap 2 來源

## Why（INCIDENT-20260601 案例）

- 2026-05-11 `fd2d421` VP-16463: 我把 PatientGrpcLogic port 到 v2（OK，那時 v1 沒 patient fallback）
- 2026-05-20 `e3d04f8` VP-16685: 我加了 v1 cloud-with-fallback，**commit msg 寫 "for all v1 lis gRPC methods including Patient" 但實際只 wire 已存在的 `getPatient`**。createPatientV2/checkPatientsName/updatePatientInfo 全沒補 → **Gap 1**
- 2026-05-?? `10da3cb` INCIDENT-2604156666: sample 從 v2 revert 回 v1，**patient 同個 server 同個 risk 沒一起 revert** → **Gap 2**
- 2026-06-01: v2 server CreatePatientV2 RPC hang → 3 個 inbound HL7 卡死，無 fallback 可用

Gap 1 + Gap 2 疊起來 = 整個 patient create path 沒 resilience。

## How to apply（pre-PR checklist）

```
□ 我這 PR 是不是在加 fallback / wrapper 基礎建設？
  → 是：grep 所有 same-namespace caller，列 migration scope，同 PR 做完
□ 我這 PR 是不是在 revert 某 RPC？
  → 是：grep 同 server 其他 RPC，做 risk assessment，把同類 caller 同步處理
□ commit message 寫 "for all X" 之前確認真的 cover all，不是只 cover existing wrapper method
```

## 同類前科

- VP-16685 `e3d04f8` commit msg "for all v1 lis gRPC methods including Patient" 實際 cover 不到一半 — message 與 code 不一致
- INCIDENT-2604156666 scope 只動 sample，沒擴展到同 server 其他 v2 caller

## 同類 memory

- [[end_to_end_equivalence]]: RPC 替換前 diff 前後 output 完全相同
- [[v1_to_emr_v2_migration_parity]]: port behavior 時逐欄位 enumerate 全 branch
- 本條 + 上兩條一起 = 「重大架構變動的 audit 要 exhaustive，不能只 spot check」家族
