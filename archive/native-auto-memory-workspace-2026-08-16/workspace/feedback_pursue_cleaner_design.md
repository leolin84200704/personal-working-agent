---
name: feedback_pursue_cleaner_design
description: "every task — actively look for the cleaner/better design and apply it, don't ship the first thing that works; but verify the \"cleaner\" claim before refactoring"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 99dcff7b-017c-4aa9-b3ee-802733ba4be2
---

每個任務都要主動想「有沒有更乾淨/更好的做法」並 apply，不要只交「第一個能動的版本」。寫更好的 code 是預設要求，不是 nice-to-have。

**Why:** Leo 2026-06-23 (VP-17117) 明確要求：「這種更好的做法一定要每次都思考並且 apply，寫更好的 code。」（情境：我先交了 post-assembly swap (B)，討論後才浮出更乾淨的 pre-pipeline swap (A)。）

**How to apply:** (1) 交方案前先問：單一職責點？少一層 hack/fallback？用權威來源而非 hardcode？對未來情境 robust？(2) **但「更乾淨」要驗證再 apply，別憑直覺斷言** —— 同一個 VP-17117，(A) 我一度說更乾淨，深查後發現 NY twin 不在 emr-v2 本地 bundle cache(getLegacyBundleMapping)，(A) 把 NY id 餵進 bestDeal→assembly `bundleIdToBundleMap.get(twinId)` 查不到→orderItem 被丟掉，反而是 (B)「從標準 bundle 建 orderItem 再換 item_id、下游 re-resolve」才正確。教訓：refactor 前先驗證新做法的隱藏相依(cache/資料/時序)，不要把未驗證的「更乾淨」當定論。相關 [[feedback_verified_means_live_not_mock]] [[feedback_prefer_stable_id_over_name_matching]]。
