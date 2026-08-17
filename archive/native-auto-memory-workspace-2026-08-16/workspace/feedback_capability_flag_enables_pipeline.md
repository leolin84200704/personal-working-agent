---
name: feedback_capability_flag_enables_pipeline
description: enabling a capability flag during backfill activates a downstream pipeline — verify supporting config exists first
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 99dcff7b-017c-4aa9-b3ee-802733ba4be2
---

設定/ backfill capability flag 前，先確認該 flag 啟用的下游 pipeline 有足夠 config 支撐。**Enable 一個 capability flag = 啟用一條 pipeline**，不是只是貼標籤。

**Why:** VP-16968 backfill 225 個 order_clients 客戶進 ehr_integrations 時，我選了 `integration_type=FULL_INTEGRATION` + `result_enabled=true`，但 order_clients 沒有任何 result 投遞 config（ehr_vendor_id / sftp_result_path / sftp_host / legacy_emr_service / msh06_receiving_facility 全 225 筆 null）。結果 225 列全部變成 result-pipeline-eligible（Kafka report-finished listener 選 `result_enabled=1 AND type∈{RESULT_ONLY,FULL}`）→ 報告完成事件一來就會被選中然後因無設定而失敗。Leo 抓到：「沒有 sftp_result_path / ehr_vendor_id... 要怎麼發 report?」

**How to apply:** (1) 對每個要設 true 的 flag，問「這啟用哪條 pipeline？那條 pipeline 讀哪些欄位？來源資料有沒有那些欄位？」`result_enabled`→result/Kafka 投遞→需 vendor + sftp_result_path；`ordering_enabled`→order 解析→需 customer_id/clinic_id/kits。(2) 來源資料缺 config 就不要 enable 那條 capability（VP-16968 改成 ORDER_ONLY + result_enabled=false，純 order 解析）。(3) 問使用者選 type/flag 時，主動講明每個選項會啟用的 pipeline 與所需 config，別只問 enum 值。相關 [[feedback_v1_to_emr_v2_migration_parity]] [[feedback_verified_means_live_not_mock]]。
