# 2026-07-27 — VP-17499/VP-17500: placerId namespace 修正 + optional 化（同日三票連環）

Related: VP-17497, VP-17499, VP-17500

## 事件軌跡

1. VP-17497 收尾後 Leo 連問三個概念題（為什麼有 placerId / 客戶怎麼填 / 全局還是 per-patient）— 回答「客戶怎麼填」時去查 uniqueness 作用域，發現 placer_id 是全域 unique、order_intake 無 customer 欄位 → **當場開 VP-17499**（兩天前才寫的 defect-must-be-ticketed 教訓第一次實際執行）。
2. Leo 確認 per-customer 是正確 scope（per-patient 有 wrong-patient-typo retry 會雙開訂單的反例），批准動工、拆 2-3 commits。
3. 關鍵設計：**expand/contract 兩段式 migration** — part A 加欄位+複合鍵（舊全域 unique 保留，因為線上舊 code 的 idempotency 完全依賴它的 P2002），part B 拆舊鍵，只能等新 code 上齊兩環境。過渡期跨租戶撞名 → 422 placer_id_conflict fail-closed。
4. Slack 上 api-product 又加需求（Tianhao）：placerId 改 optional、不給就完全不去重（portal parity）→ **VP-17500**，疊在 VP-17499 branch 上（stacked PR #293 base #292，GitHub merge 後自動 retarget）。實作選 server 生成 AUTO-<uuid> key 而非 nullable 欄位 — 零 schema 變更、row 照留（audit/payment 追蹤）、結構上不可能去重。
5. Leo 同日 merge + deploy；E2E 全過（無 placerId 兩張獨立單 / duplicate 回歸 / reclaim 回歸）；Confluence 推到 v15。

## 探索中排除的

- per-patient scope：idempotency key 識別的是 request 不是 patient 關係；typo-patient 修正重送場景會失效。
- nullable placer_id（VP-17500）：schema churn + MySQL NULL-dup 語意讓 service-token 路徑失去保護；AUTO key 乾淨得多。
- 先拆舊 unique 再部署：會讓 prod 在 promotion 前完全沒有防重複下單保護 — 這是 part A/B 拆開的全部理由。

## 值得記的

- **deployment.status.readyReplicas 在 rolling update 期間計入舊 pod** —「spec image 已更新 + ready≥1」是假完成訊號，害我對舊 pod 跑了一輪 E2E（30 分鐘）；正確判準 = 新 image 的 POD 本身 containerStatuses ready。另見過一次 phantom image 讀值（ef36ced665e...，不存在的 sha）。
- MCP Atlassian 沒有 Confluence 寫入工具；`.env` 的 JIRA_API_TOKEN 走 Confluence REST v2 可直接 PUT 頁面（同一個 Atlassian token 兩用）。
- 一天內 idempotency 語意改三次（reclaim → per-customer → optional），每次都是「回答使用者問題時暴露下一層問題」— 對外 API 的 doc 問答是很好的 defect 探測器。

## Leo 原話

「全局唯一應該不合理吧」「做，拆成2-3個commit」「我merge了 #292 和 #293 + deploy 了, 請跑E2E測試」
