---
name: project_fhir_order_api_study
description: FHIR inbound order API feasibility study for lis-backend-emr-v2 — verdict and key findings
metadata: 
  node_type: memory
  type: project
  originSessionId: 415441e0-9454-43ef-9b77-d562eb682e10
---

2026-06-06: Leo 委託深度評估「在 lis-backend-emr-v2 新增 FHIR-based inbound order API（取代 SFTP HL7 folder upload，不需帶 report）的限制/困難點」。產出 `/Users/hung.l/src/FHIR-ORDER-API-FEASIBILITY.md`（13-agent workflow，含 HL7 v2 vs FHIR 深度比較）。

**裁定：條件式 GO，但原生 FHIR 不是 MVP 正確形態。** Gate 1 = 須先有具名、堅持用 FHIR ServiceRequest 下單且抗拒 SFTP 的 vendor，否則 premature → NO-GO。

**已驗證的可重用骨架**（codebase 逐行確認）：`OrderFinalizerService.finalize()` 吃已組裝的 `OrderFrontend`+`UserPayload`+`CustomerDetailsParams`、**零 HL7 依賴** → 任何新前門（FHIR/JSON/HTTP-HL7）都能餵它。下游（transactionPay 刷卡 → sendOrder → emr_sample）100% 可重用。`dryRun` shadow-compare hook + `parser.service.spec.ts` 的 revolution-health ground-truth diff harness 可做 parity 測試。

**三大真實難點**（依難度，非 FHIR 解析本身）：
1. 含不可逆刷卡的同步請求 exactly-once — 冪等鍵須在刷卡**前**生效（先寫 intake row + unique constraint on placer identifier），否則 vendor HTTP retry 會雙重扣款。現行 `findExistingSampleId` 只在 emr_sample 寫入後才去重，不夠。建議 202+BullMQ+Task 而非同步 201。
2. 信任模型整換 — 零 OAuth2/SMART/mTLS，只有 HS256 內部 JWT。`JwtAuthGuard` 對 FHIR payload 失效（租戶鍵在 requester/identifier 非扁平 customer_id → 落入 validateGeneralAccess default-allow）。須新建 FHIR-aware default-deny Guard + resource-server scope enforcement。禁止把 HS256 對稱密鑰給外部 vendor。
3. test code 映射（**被高估**）— MVP 要求 partner 送 Vibrant code 直接丟 `classifyBatteryId`（須抽 private→public）= S；SFTP 路徑現在就這樣運作。只有自建 LOINC→catalog compendium 才是 XL。

**「不帶 report」的隱性新問題**：order 成功隱性綁定 result-routing config（ehr_integrations.integration_type/msh06/sftp paths）。FHIR-native vendor 多無 SFTP outbound → 孤兒 order；placer identifier↔HL7 control_id 對應須下單時持久化否則結果無法閉環。

**最大盲點**：dual-path-forever 維護稅（SFTP 不會消失），18 個月 TCO 可能超過 build 成本。

**替代方案**：精簡 JSON API（最便宜 S~M，可順手解冪等）或接中介（Health Gorilla 還在 STU3、Redox 把 FHIR 降轉回 ORM^O01 餵現有 SFTP）。法規面：ONC g10 只強制 FHIR 讀結果，**不強制也不標準化 FHIR 寫訂單**。

相關：[[project_emr_cloud_migration]]、[[feedback_end_to_end_equivalence]]、[[feedback_v1_to_emr_v2_migration_parity]]
