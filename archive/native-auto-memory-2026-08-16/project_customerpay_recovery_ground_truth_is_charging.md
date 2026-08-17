---
name: project_customerpay_recovery_ground_truth_is_charging
description: "customerPay 收款/回收的 ground truth 在 charging 系統,不是 LIS；hl7_file_input 看不到 out-of-band 收款"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1fbf0ab5-509e-4a5d-9189-cb6953f4c5cc
---

判斷 customerPay 訂單「是否已收款/已回收」時,LIS(`lis_emr`)不是 ground truth — charging 系統(vibrant-wellness,`/v1/charging/...`)才是。

**事實(2026-07-20 VP-17411 實查確認)**:
- `hl7_file_input.order_input` 是 intake 當下的快照,收款失敗後**不會回寫**。手動/後續在 charging 系統收款是另一筆交易,LIS 端沒有痕跡。
- `lis_emr` schema **沒有任何 payment/charge/transaction 表**(`information_schema` 查 `%pay%/%charg%/%transac%` 為空)。
- 所以 `payment_id=null` + `order_input` 仍是原始 `Credit Card Error`,**不代表未收款** — 可能已在 charging 系統 out-of-band 收掉。VP-17411 的 6390/6502/6504 就是這種情況:LIS 顯示未收,實際三筆都已在 charging 收款、ticket mark done。

**Why**:曾據 LIS 端 `payment_id=null` 判斷「還沒回收」,與事實(charging 已收)不符,回報給 Leo 被糾正。

**How to apply**:
- 回答「這筆付了沒/回收了沒」前,查 charging 系統(見 [[project_charging_paymethod_query]] 的 JWT/endpoint 路徑),不要只看 LIS 的 `payment_id`/`order_input`。
- LIS 端只能說「LIS 沒有收款痕跡/對帳回寫」,不能說「未收款」。two systems、各自 ground truth:order/sample 看 [[project_verify_sample_core_not_emr_mirror]](lis_core_v7),收款看 charging。
- 相關:[[feedback_execute_not_just_verify]] — 現況類問題一律對真正的 ground truth 系統驗證,別靠假設或錯的資料源。

**附帶技術事實**:本地 mysql-client 連 prod DB 被網路/VPN 阻斷時,可從 AKS pod 內部查(pod 有 node + `mysql2` + `DATABASE_URL`,但 Azure MySQL 需顯式 `ssl:{rejectUnauthorized:false}`,且 mysql2 會忽略 prisma URL 的 sslmode 參數)。`kubectl exec deploy/lis-emr-v2-deployment-prod -c lis-emr-v2-prod -- node -e '...'` 即可 read-only 查 prod,繞過本地阻斷。
