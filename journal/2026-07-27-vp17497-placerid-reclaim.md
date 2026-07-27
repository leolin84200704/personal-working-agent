# 2026-07-27 — VP-17497: placerId 卡死 triage → 一天內修完（reclaim + payment replay）

Related: VP-17497, VP-17283, VP-17286, VP-17475

## 事件軌跡

1. Leo 轉來 Tianhao（api-product）的 Slack：sandbox 下單回 `201 {status:duplicate, sampleId:null}`，跟 mintlify doc 的 idempotency 描述不符。
2. 檢索：STM VP-17286 scope item 7 **早在 2026-07-13 就記錄了這個 wrinkle**（placement-failed placerId 永久卡死，proposed follow-up 沒排）。這次是 memory 直接命中 root cause 的案例 — 先讀 index 再讀 STM 的紀律有回報。
3. Ground truth：staging pod 路由查 order_intake → id=62 status=ineligible (IncompletePatientInfo)，07-22 第一次請求就失敗，之後全被 duplicate 短路。patient 3226427 不在 staging lis_core_v7（patient 來自 v2 GetPatient gRPC，不同 source）— 沒深追，eligibility 判定是 order team 的 API。
4. 對 Leo 報告時給了 A（改 code）/B（改 doc）選項；Leo 反問「本意就是補齊資訊重下單」= 確認 A 方向，並揪出真正的設計問題：terminal failure 不該佔用 idempotency key。
5. 關鍵風險自己找到的：finalize 是 charge-first，`failed` row 可能已收費 — 盲目 retry 會重複收費。所以 Phase 1（無 schema、safe statuses）/ Phase 2（存 payment 再放開 failed）拆開。Leo 拍板兩個都做、分 commit。

## 探索中排除的

- 「刪 row 釋放 key」— 損失 audit trail（本次 triage 就靠 row），且 status-gated atomic UPDATE 同樣防併發。
- 「duplicate 時 replay original result」（動對外 contract）— 不做，doc 微調即可。
- mintlify doc source repo — gh org list 找不到，應該在 api-product 團隊手上，wording 草稿交給 Leo。

## 值得記的

- ORDER-PIPELINE.md §2.6 早就「承諾」了 retry-same-placerId + payment replay 不重複收費 — doc 寫了沒實作。doc 先行於 code 的 drift 是這個 repo 的既有 pattern（Confluence spec 也常領先 impl）。
- finalize 的 HL7 replay 機制（parseOrderInfo.sample_id_payment）直接復用到 API path，Phase 2 幾乎零新邏輯 — 讀懂舊機制比發明新機制省。
- pre-commit guard-1 的 ORDER_INTake_MODE false positive 第三次出現（VP-17286/17475/本次）— 也許該修 hook 讓它只看新增的 env var。
- Gate 3 執行：ALTER 先套 staging+prod 再開放 merge；prod 欄位 nullable、promotion 前無讀者，安全。
- Dream pipeline 疑似停擺（STM index 停在 07-23）已回報 Leo。

## Leo 原話

「照理說合理的方式應該是…把request 丟掉但不佔用 placer_id」「我們的本意就是要補齊資訊後重新下單」「Phase 1 先做，Phase 2 一起做但是不同commit, 然後doc 也要改」
