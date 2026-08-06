---
date: 2026-07-02
slug: report-finished-pre-golive-drop
related_tickets: []
distilled: true
archived: 2026-08-05
---

# report_finished event 早於 integration go-live 被靜默丟棄（accession 2606116259 / 2606116226）

## Context
Leo 問：兩個 accession（2606116259 / 2606116226，sample 3240966 / 3240947，customer 51154，clinic 154338）明明有收到 report_finished kafka message（2026-06-22T18:12Z），為什麼 lis-emr-v2 沒發 result。要求看 code 找問題。

## What we explored
- 讀完整條 result pipeline：`kafka-report-finished-listener.service.ts` → `result-queue.service.ts` → `result-generation.processor.ts` → `result-generation.service.ts#generateResultHl7`。
- 排除 pipeline 執行失敗：generateResultHl7 內所有失敗路徑都會更新 result_transmission_records 並 throw（BullMQ retry x5）。若 job 有跑過，DB 一定有 row。
- 排除 SFTP singleton hang（已知 pattern）：那會留下 GENERATING/ERROR record，這次是 0 rows。
- Prod DB（lisportalprod2 / lis_emr，read-only，經 repo node_modules 的 mysql2 + .env DATABASE_URL）實查：
  - `result_transmission_records` sample 3240966/3240947 → **0 rows**（event 根本沒進 pipeline 的特徵）。
  - customer 51154 的 ehr_integration `cmqpt82jr00050xreyprgasoc`（FOLLOWTHATPATIENT, FULL_INTEGRATION, result_enabled=1, LIVE）**created_at = 2026-06-23T05:51Z** —— 比 event 晚 ~11.5 小時。status history 0 rows（一開始就以 LIVE 建立）。
- Root cause：event 到達時 `findEligibleResultIntegrations` 回空 → listener `:268` 直接 `return`，offset 照 commit，event 永久消失。不是邏輯 bug，是時序 + 設計缺口。

## Decisions
- 判定為三個 code 層級缺口（尚未修，僅回報）：
  1. 查無 integration 時靜默丟棄，只有 `logger.debug`（prod 看不到），DB 無痕跡。
  2. integration 轉 LIVE / 開 result_enabled 時**沒有 backfill** 上線前已 finished 的 report（與 VP-16968「開 flag = 只對未來生效」同族教訓，但方向相反：這次是 flag 晚開）。
  3. `handleMessage` catch-all 吞錯後 offset 一樣 commit → transient DB error 也會永久丟 event。
- 補救路徑已指出：`result.service.ts#generateResultHl7(sample_id)` 手動觸發可補發。Leo 回「done」→ 本 session 不補發、不開 ticket，結案。

## Files touched
- 無 code 變更。僅 scratchpad 查詢腳本（session-local）+ 本 journal。

## Open questions / followups
- 這兩筆 result 是否已由 Leo 手動補發？（session 內未確認）
- 「go-live backfill + 靜默丟棄可觀測性」是否要開 improvement ticket——Leo 未表態。
- debug 手法可重用：repo 本地 .env 的 DATABASE_URL + node_modules/mysql2 直查 prod（不需 mysql client / pod exec）。

## User feedback this session
- 無 correction。結尾「done」= 結案，不需進一步動作。
