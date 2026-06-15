---
id: fhir-api
type: ltm
category: emr_integration
status: active
score: 0.693
base_weight: 1.0
created: 2026-06-06
updated: 2026-06-06
links:
- HL7-TRIAGE-20260427
- INCIDENT-2604156666
- LBS-1541
- QH-1660
- QH-2257
- QH-2577
- QH-3752
- QH-4350
- QH-4352
- QH-4608
- QH-5840
- VP-14787
- VP-15279
- VP-15952
- VP-16014
- VP-16157
- VP-16164
- VP-16166
- VP-16175
- VP-16180
- VP-16186
- VP-16193
- VP-16233
- VP-16245
- VP-16251
- VP-16271
- VP-16280
- VP-16289
- VP-16329
- VP-16379
- VP-16396
- VP-16423
- VP-16424
- VP-16463
- VP-16476
- VP-16617
- VP-16685
- VP-16720
- VP-16734
- VP-16765
- VP-16766
- VP-16784-87
- VP-16832
- VP-16881
- VP-16885
- VP-16934
- emr-integration
- repos
tags:
- fhir
- hl7
- emr
- integration
- order-api
- smart-on-fhir
- api-versioning
summary: HL7 v2 vs FHIR deep reference + feasibility of a FHIR inbound order API for
  lis-backend-emr-v2 (no report), reuse map, difficulty ranking, and Epic/Story/Ticket
  breakdown for future creation
---














































# FHIR for lis-backend-emr-v2 — Reference & Build Plan

> 蒸餾自 2026-06-06 的 13-agent 可行性研究。完整文件：`/Users/hung.l/src/FHIR-ORDER-API-FEASIBILITY.md`（1508 行，含 PM/架構師/QA/Security 角色分析 + 對抗審查 + web research 原文）。
> 用途：(1) HL7 v2 ↔ FHIR 知識基礎；(2) 未來要 create FHIR-related Story/Epic/Ticket 時的權威拆解來源。

---

## 1. 一句話結論

在 lis-backend-emr-v2 加一個非 SFTP 的 inbound order 前門**技術可行、下半身可原封重用**；但**原生 FHIR 不是 MVP 正確形態**，除非有具名、堅持用 FHIR ServiceRequest 下單且抗拒 SFTP 的 vendor（**Gate 1**）。真正難點不在 FHIR 解析，而在：刷卡冪等正確性、信任模型重建、dual-path TCO。

## 2. HL7 v2 vs FHIR — 根本差異（reusable knowledge）

**最深一條**：FHIR 把「訊息（瞬時指令）」變成「資源（可 GET / 版本史 / conditional upsert 的持久狀態）」。這與 emr-v2 既有的「fire-and-forget + cron 自癒 + 一次性刷卡」**根本對沖**。

| 面向 | HL7 v2（現行 SFTP 路徑） | FHIR R4 |
|---|---|---|
| 線材 | pipe-hat、**CR(0x0D) 結尾**（非 LF/CRLF，最常見 parser 失敗源）；delimiter 由 MSH-1/2 動態宣告 | JSON/XML 資源樹，schema 驅動 |
| 傳輸 | 檔案 drop(SFTP) → cron → BullMQ，**非同步 store-and-forward** | RESTful POST Bundle，**預設同步** |
| 訂單模型 | `ORC`(order control)+`OBR`(test)+PID/PV1/IN1/GT1/DG1/SPM/AOE-OBX | `ServiceRequest`(=ORC+OBR)+Patient/Coverage/Specimen/Practitioner/Organization/Condition/AOE-Observation |
| 操作意圖 | `ORC-1`(NW/CA/HD/DC…)，**非** trigger event | `ServiceRequest.status`+`.intent` |
| 冪等鍵 | `MSH-10` control id（`findExistingSampleId` 去重）| `ServiceRequest.identifier`(placer)+conditional create `If-None-Exist` |
| 確認 | ACK：MSA-1 AA/AE/AR、MSA-2 echo MSH-10；訂單回 ORR^O02/ORL^O22 | HTTP 2xx/4xx + `OperationOutcome`(含 FHIRPath 指出錯欄位) |
| 信任 | **周界信任**：有 SFTP key/在網內即可寫整個 folder | **零信任 per-request**：scoped、短命 token、密碼學 client identity(SMART/OAuth/mTLS) |
| 後狀態 | 無，訊息 transient | 每資源穩定 URL、版本史、可 search/upsert |

**關鍵 insight**：OBR-4 → `ServiceRequest.code` 的代碼地獄**逐字搬過去**（仍混 LOINC/local/proprietary，仍需 per-client compendium）。**FHIR 沒消除方言問題，只換載體。** US Lab Order IG 還在 ballot — **write 方向的「標準相容紅利」是幻覺**。FHIR 唯一明確優於 SFTP 的核心價值 = **同步、結構化 ACK**（OperationOutcome 讓 vendor 當場知道接受/拒絕與原因）。

**法規定位（不可誇大）**：ONC §170.315(g)(10) 是 **READ-ONLY**、scope=USCDI，**USCDI 不含 lab order placement**。Cures Act 推 FHIR 讀結果，**不強制也不標準化 FHIR 寫訂單**。故 FHIR order API = 私有 vendor API，**不需 Inferno/Drummond g10 認證**（MVP 不納入避免過度工程）。HIPAA 全面適用無豁免。

## 3. 現狀 inbound order 流程（FHIR 要替代的對象）

`Hl7OrderFetchService`(cron 掃 SFTP) → 下載 ORM/OML 檔 → `hl7_file_input` row → BullMQ `process-hl7-file` → `Hl7OrderProcessor`(`hl7-order.processor.ts`)：normalizeMessageType(OML→ORM) → decode → `resolveIntegration(npi=ORC.12/OBR.16, MSH.4)` → `parserService.parse()` → control_id dedup → `orderFinalizer.finalize()`（transactionPay 刷卡 → sendOrder POST api.vibrant-wellness.com → 寫 emr_sample → archive）。

## 4. 重用 vs 淨新增（**codebase 逐行驗證過**）

| 元件 | 狀態 | 證據 |
|---|---|---|
| `OrderFinalizerService.finalize()` | **原封重用**（吃 `FinalizeInput`，零 HL7） | `order-finalizer.service.ts:36,244` |
| `sendOrder` / `ChargeClientService` / `dryRun` hook | **原封重用** | order-test-client:66 / charge-client:38 / finalizer:48 |
| `OrderMappingCacheService`（10 個 Map，catalog API 載入） | **原封重用** | order-mapping-cache.service.ts |
| `classifyBatteryId`（OBR code 5-way 分類）| **重用，但須先 private→public 重構** | obr-parser.service.ts:189 |
| `parseObr()` | **不可重用**（簽章吃 Hl7Segment + MSH/OBR 偏移）| obr-parser.service.ts:78,150 |
| `CustomerDetailFetcherService.fetchByNpi()` | **原封重用**（吃 NPI string）| :63 |
| patient fetcher | 重用子方法 `getPatientInfoFromGrpc`+`createPatientV2`（頂層吃 PID segment）| :155,181 |
| `resolveIntegration`（NPI identity） | **重用**（NPI 來源換 FHIR requester）| processor:290 |
| `UserPayload` | **須偽造 system payload**（parser 內聯硬編 `bolin.l`/`54674`/`admin`）| parser.service.ts:179-183 |
| FhirOrderController / mapper / profile 驗證 / SMART auth / intake表+Task | **全 NET-NEW** | — |

**內部契約檔**：`dto/order.dto.ts`(`OrderFrontend`/`OrderItem`)、`dto/parse-models.dto.ts`(`PatientDetailsParams` 28欄/`CustomerDetailsParams` 22欄/`OBRHL7`)、`token-helper.service.ts`(`UserPayload`)。

**Auth 現況**：只有 passport-jwt / HS256 / `JWT_SECRET`。`JwtAuthGuard` 從 body/params/query 取扁平 `customer_id`/`clinic_id`，無則落 `validateGeneralAccess` **default-allow** → **FHIR payload(租戶鍵在 requester/identifier) 會繞過授權**。零 OAuth2/SMART/mTLS/FHIR。

**precedent**：`charm-ehr` 是唯一 api_enabled vendor，但是 **outbound、HTTP-transported HL7 v2**(text/xml+basic auth)，非 FHIR。

## 5. 限制與困難點（依真實難度排序）

1. **【最難・M~L】含不可逆刷卡的同步請求 exactly-once** — vendor HTTP retry 會雙重扣款（`findExistingSampleId` 只在 emr_sample 寫入後去重）。**冪等鍵須在刷卡前生效**：先寫 intake row + unique on placer `ServiceRequest.identifier`。建議 **202+BullMQ+Task** 而非同步 201。須查證 stax gateway 是否支援 idempotency key。
2. **【難・L／gateway後M】信任模型整換** — 須 SMART Backend Services(client_credentials + RS384/ES384 JWT assertion + per-vendor JWKS + scope)。**最危險是 resource-server 端 enforce**（~60% FHIR API 死在 BOLA/IDOR）。須新建 **FHIR-aware default-deny Guard**：server 端 client_id↔授權 ehr_integrations 集合權威映射，逐筆 requester NPI/clinic 比對，越界整單 reject。**禁止重用 HS256 對稱密鑰給外部**。
3. **【中・S~M／曾被高估為XL】test code 映射** — MVP 要 partner 送 Vibrant code 直接丟 `classifyBatteryId` = S（SFTP 路徑現在就這樣）。只有自建 LOINC→catalog ConceptMap 才 XL。
4. **【中・M】身分抽取/Patient/Specimen/diagnosis/跨前門 dedup 衝突** — NPI 藏在 `Practitioner.identifier`(可能 contained/urn:uuid)；同 vendor 同走 SFTP+FHIR 時 MSH-10 vs placer id 不同源 → **雙重下單風險**。
5. **【中・MVP-S/完整-L】FHIR 驗證/Conformance** — package.json 零 FHIR 套件。MVP=`@types/fhir`+手寫 defensive 驗證+OperationOutcome，只接 R4。完整(HAPI validator+US Core+CapabilityStatement)列 out of scope。
6. **【最大盲點・複利】Dual-path-forever 維護稅** — SFTP 不會消失；雙路徑共用同一下半身，每改 finalizer/mapping/identity 都雙路徑回歸；冪等/observability/runbook 分裂。18 個月 TCO 可能超過 build 成本。

## 6. 「不帶 report」的隱性陷阱

- order 成功隱性綁定 result-routing config(`ehr_integrations.integration_type`/`msh06`/`sftp_*`)。**FHIR-native vendor 多無 SFTP outbound → 孤兒 order**（下得進、結果無處回）。
- closed-loop：`DiagnosticReport.basedOn→ServiceRequest` vs HL7 ORU 靠 placer/filler+control_id。**placer identifier↔HL7 control_id 對應須下單時持久化**，否則結果無法 reconcile。
- 付款缺口：FHIR ServiceRequest 無付款 token；charge 用 `customerInfo.customer_id` 查 stax on-file → FHIR vendor 必須是已建好且有付款 token 的 customer（onboarding 變商務/KYC 問題）。

## 7. 替代方案

| 選項 | 工作量 | 備註 |
|---|---|---|
| 原生 FHIR | 完整XL/MVP M~L | 生態入場券；但 write-FHIR 小眾，HG 還在 STU3 RequestGroup → 做 R4 仍要寫版本轉接（自我反駁）|
| **精簡 JSON API** | **S~M(最便宜)** | 省 §5.5；mapper 近 identity；可原生設計「先寫 intake 再刷卡」直接解 §5.1 |
| CHARM 式 HTTP-HL7 | S~M(parser 全重用) | 但 auth/PHI/稽核三案等價貴；basic auth 對外不可接受 |
| 第三方聚合(Health Gorilla/Redox) | 趨近零 | Redox 直接把 FHIR 降轉回 ORM^O01 餵現有 SFTP；但吸走 native FHIR 唯一價值(同步互動) |

**洞見**：「支援 FHIR ordering」實務上常 = 「支援一個會把 v2 交給我們的中介」。

---

## 8. Epic / Story / Ticket 拆解（未來 create 用）

> 若 Gate 1 通過、決定 build，建議結構如下。標 `[P0-spike]`=先做驗證，其餘依 phase。

### EPIC: Non-SFTP Inbound Order Intake API (FHIR/JSON) for lis-backend-emr-v2
**Goal**: 提供 EMR vendor 一個同步、結構化 ACK 的 inbound order 前門，重用既有 finalize 下半身，與 SFTP 路徑並存。
**Gate**: 須有具名 vendor 需求（Gate 1）才啟動 Phase 1+。

#### Phase 0 — Spike（先做，~1 sprint）
- **Story [P0-spike] Synthesized-OrderFrontend → finalize(dryRun) 可行性驗證**
  - Ticket: 合成 hard-coded `OrderFrontend`+偽造 system `UserPayload` 呼叫 `finalize({dryRun:true})`，確認下游可吃
  - Ticket: 延伸 `parser.service.spec.ts` 的 revolution-health ground-truth diff harness，對同一張訂單比對 FHIR/JSON-adapter 輸出 vs HL7-parser 輸出，`expect(diffs).toEqual([])`
  - Ticket: 查證 stax/charge gateway 是否支援 idempotency key（決定 §5.1 能否乾淨解）
  - Ticket: 盤點現行 parser 是否處理 AOE(order-OBX)；查 Vibrant 是否已有 LOINC→catalog ConceptMap 及覆蓋率

#### Phase 1 — MVP Pilot（走 JSON 或 HTTP-HL7，非原生 FHIR）
- **Story 內部契約 + 前門骨架**
  - Ticket: 抽 `classifyBatteryId` private→public（最小重構）
  - Ticket: 新建 `FhirOrderController`/`OrderIntakeController`（versioned `/api/v2/orders` 或 `/fhir/r4`）
  - Ticket: 新建 `*ToInternalMapperService`：請求 → `OrderFrontend`/`PatientDetailsParams`/`CustomerDetailsParams`/`OBRHL7`（薄 mapper，近 identity；重用 fetchByNpi/getPatientInfoFromGrpc/createPatientV2/OrderMappingCache）
- **Story 冪等 + 非同步**
  - Ticket: 新建 intake 表（unique on placer identifier，**刷卡前**生效）+ Prisma schema（記得 prod 無 _prisma_migrations，用 SHOW COLUMNS 驗）
  - Ticket: 202 + Task 狀態機 + 走既有 BullMQ retry 基建 finalize
  - Ticket: 跨前門 dedup — placer id 映射進 control_id 共用 `findExistingSampleId`（防 SFTP+API 雙投雙扣）
- **Story 認證/授權（最低門檻）**
  - Ticket: 獨立非對稱信任鏈（client_credentials + per-vendor JWKS；或 front Azure Health Data Services/Auth0 處理 token）；新 env 同 PR 更新兩份 config-yaml
  - Ticket: **FHIR-aware default-deny Guard** — client_id↔授權 ehr_integrations 集合，逐筆 requester NPI/clinic 比對，越界整單 reject；hard-enforce `ordering_enabled`/`integration_type`
  - Ticket: resource-server scope enforcement + 負向測試(.cud token 不得 read/碰他型別)
- **Story 安全/合規 MVP**
  - Ticket: FHIR 來源 order 預設進人工放行佇列/dryRun，不直接觸發刷卡，直到信任建立；per-client rate limit + 額度上限
  - Ticket: AuditEvent → WORM/SIEM；app log 去識別化禁 PHI
  - Ticket: 限夥伴網段起步；per-vendor BAA
- **Story Onboarding 必填**
  - Ticket: result-routing config 強制（防孤兒 order）+ placer↔control_id 持久化
  - Ticket: payment token 設定前置（customer 須已建好且有 stax token）

#### Phase 2 — 視需求
- transaction Bundle(urn:uuid 解析、原子化)、conditional create idempotency、AOE(supportingInfo)、Patient/Specimen/diagnosis adapter、Task 全狀態機

#### Phase 3 — 只在具名 FHIR-write vendor 成立時
- 原生 FHIR profile、STU3 RequestGroup 相容(接 Health Gorilla)、`$validate`、CapabilityStatement、mTLS、(若 PM 要)Inferno/Touchstone g10

**每期鐵律**：任一前門上線同 PR 規劃 SFTP 退場或明確接受 dual-path 永久稅；冪等鍵刷卡前生效；onboarding 強制 result-routing+payment token；新 `process.env.X` 同 PR 更新兩份 config-yaml。

## 9. 給 PM/vendor 的 Gate 問題（create discovery ticket 用）
1. 有無**具名 vendor** 要 FHIR ServiceRequest 下單且抗拒 SFTP？送 R4/STU3/還是透過中介(降轉 v2)？
2. 獨特價值是否是「同步結構化 OperationOutcome」？若可接受非同步對帳 → 接中介(buy) 不 build
3. Code crosswalk：partner 送 Vibrant code(S) 還是要我們建 LOINC→catalog compendium(XL)？
4. stax gateway 支援 idempotency key？
5. 同一 vendor 是否同走 SFTP+新前門？placer id 與 MSH-10 如何共用去重？
6. FHIR vendor 有無 SFTP outbound？placer↔control_id 持久化在哪？
7. 認證 infra owner：自建 SMART token endpoint 還是 front Azure Health Data Services？要 mTLS？
8. 同步 201 vs 202+Task：partner EHR 會 poll/收 webhook？
9. legacy Java V1 並存：此 vendor 訂單是否還經 V1？FHIR 進 V2 不被 V1 看到 → 資料分裂(parity)
