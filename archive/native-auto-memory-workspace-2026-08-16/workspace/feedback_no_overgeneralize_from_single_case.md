---
name: no-overgeneralize-from-single-case
description: 歸納 knowledge/LTM 規則前先 cross-check 多個過去 case 的真正原因，不要從單一 case 反推普遍規則
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0733c023-6899-4f28-bbd7-936ee89938ea
---

寫入 LTM/knowledge 的「通則」前，先 grep 多個過去 case，確認該值/行為在每個 case 的**真正原因**；不要從單一 case 反推出普遍規則。

**Why:** VP-16734（Cerbo stub finalize）時，我看到 VP-16424 用 `report_option=CLASSIC`，就反推出「stub 原本是 CLASSIC 就保留不覆寫」的假規則，還寫進 LTM emr-integration.md。Leo 指正「這個邏輯有誤，請看一下之前是怎麼做的」。實際 grep VP-16423/16245/16424 後發現：CLASSIC 出現的原因各不相同 —— (a) follow same-clinic 既有值剛好是 CLASSIC，或 (b) Leo 當時一次性指示採 stub schema default。通則其實一直是 `PERSONALIZED`（= Field Default）。我把一個個案的特殊處理當成了普遍規則。

**How to apply:** 在 [[feedback_lis_code_agent_first]] 的 Work Loop Step 9（Memory Update / 記憶蒸餾）寫 LTM 規則時，若規則來自觀察過去 ticket 的某個欄位值/做法，先 `grep` 至少 2-3 個相關 STM，逐一確認那個值的成因（是 follow existing？個案指示？真正預設？）。成因不一致時就不要寫成「通則」，改寫「預設是 X，遇到 Y 情況跟 Leo 確認」。Leo 說「看一下之前怎麼做的」= 要求做這個 cross-case check，不是讀單一 case。
