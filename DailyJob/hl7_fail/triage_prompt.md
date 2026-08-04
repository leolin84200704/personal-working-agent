## hl7_file_input Daily Triage

執行以下完整流程，結果輸出到 `/Users/hung.l/src/vibrant-america-working-agent/DailyJob/hl7_fail/` 目錄下，檔名格式 `triage_{YYYY-MM-DD}.md`。

### 連線資訊
- Azure MySQL: host=lisportalprod2.mysql.database.azure.com, port=3306, user=lis_core_emr, password=md?At3pUJnS2?Zx68, db=lis_emr, ssl-mode=REQUIRED
- Order API (prod): POST https://www.vibrant-america.com/lisapi/v1/portal/order/orderTest/order
- Payment Methods: GET https://www.vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods
- TransactionPay: POST https://www.vibrant-america.com/lisapi/v1/charging/transaction/pay
- Bundle Mapping (VACP only): GET https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd
- Package Price Mapping (VATEST/VAREQUISTION): GET https://api.vibrant-wellness.com/v1/pricing/item/price/getLegacyPackagePriceMapping?currency=usd
- JWT prod secret: 從 /Users/hung.l/src/EMR-Backend/src/main/resources/dependencies/orderApi.yaml 的 jwtSecret.prod 讀取
- Bundle mapping API token: 從同檔案 orderApiToken.prod 讀取

### Step 1: 查詢失敗記錄
```sql
SELECT id, file_name, emr_code_not_found, sftpDir, emr_service, retry_num, parse_finished, received_time, LEFT(order_input, 2000) as order_input
FROM hl7_file_input
WHERE parse_finished = 0 AND retry_num = 0 AND received_time >= NOW() - INTERVAL 72 HOUR
ORDER BY received_time DESC;
```
如果無記錄，寫 "No failed records found" 到報告檔案並結束。

### Step 2: 分類失敗記錄
- **Type A (emr_code_not_found):** `emr_code_not_found` 有值 → VACP 或其他 code 問題
- **Type B (order failure):** `order_input` 有值 且 `emr_code_not_found` 為 NULL → payment/order 失敗
- **Type C (parse failure):** `order_input` 為 NULL 且 `emr_code_not_found` 為 NULL → HL7 parse exception

### Step 3: Type A 處理 — Code 分析（依 prefix 選 API，不要全部用 bundle mapping）

> 2026-07-10 教訓：舊版此步驟對所有 code 都查 bundle mapping，導致 VATEST79（05-22）和
> VATEST2287 等 6 個 code（07-09）被誤診為「not found in mapping」— 用對的 API 重查後全部
> 存在，真因是 isOrderable=false / priceVa=-1（catalog 設定缺口）。lookup path 已對照
> emr-v2 `obr-parser.service.ts` / `order-mapping-cache.service.ts` 與 Java `ParseHL7.java` 確認。

1. 把 `emr_code_not_found` 以逗號拆開，**每個 code 依 prefix 分別查**（同一筆內 prefix 可能混雜）：
   - **`VACP{panelId}`** → Bundle Mapping API，比對 `oldOrderTypeId == panelId`
   - **`VATEST{orderTypeId}`**（單項測試）→ Package Price Mapping API（dict key 是數字 id），
     比對 `orderTypeId`；找到後**必須檢查 `isOrderable === "true"`** — 存在但 isOrderable=false
     會被 parser 當作 not found，落入 emr_code_not_found 的方式跟真的不存在完全一樣
   - **`VAREQUISTION{groupId}`**（panel/requisition）→ 同 Package Price Mapping API，但用
     lowercase EMR code 比對 `emrCodeToPackagePriceMap`；同樣有 isOrderable 閘門
   - 其他 prefix → 兩個 API 都查過再下結論，並在報告標記「未知 prefix」
2. 用 sftpDir 反查 order_clients → ehr_integrations 取得 clinic_name, clinic_id, customer_id
3. 記錄時**區分三種診斷**（處方不同，寫錯會把 PM/order team 帶去錯的方向）：
   - `code 不存在` → 需要 pricing 註冊新 code
   - `存在但 isOrderable=false / priceVa=-1` → catalog 設定缺口（開 isOrderable + 補 VA 價，
     或確認該測試應改走 panel）——**不是**註冊新 code
   - `存在且 orderable，但未分配給該 customer/clinic` → 分配問題
   找到的 code 一律附上 `isOrderable` 與 `priceVa` 欄位值作為證據

### Step 4: Type B 處理 — 手動 Payment + Order Recovery

> 錢的操作不靠判斷力自律，靠確定性閘門。以下 4.0/4.5 的每個 guard 都對應真實事故：
> 6517/18/20（2026-07-02）「失敗」的原始 attempt 其實已在 server 端建單，缺 pre-check 差點重複下單；
> 2xx 無 transaction id 曾被當成功導致無聲未收費出貨（VP-17411）。

**Step 4.0 — 收費前置檢查（每筆，任一不過就跳過收費、標「需人工」）：**
1. 重新 SELECT 該 row，確認仍 `parse_finished=0` 且 `payment_id IS NULL` — 不信 Step 1 的快照
2. 查 core ground truth（`lis_core_v7.sample` + `order_info`，本機連不上就從 AKS pod 內查；
   **不可用 `lis_emr.emr_sample` mirror 判斷**）：該 patient 在 order 時間窗內有無既有 active
   sample。有 → 上次 attempt 可能已成功，絕不再收費，記錄 sample_id 標人工核對
3. 檢查 recovery ledger（`DailyJob/hl7_fail/recovery_ledger.jsonl`，一行一 JSON
   `{"id":..., "date":..., "step":...}`）：該 hl7_file_input id 已出現過 → **永不再收費**，
   標「曾嘗試過，需人工」。這個檔案是防重複收費的最後防線 — 就算流程中斷重跑也擋得住

對每筆通過 4.0 的記錄：
1. 從 order_input JSON 提取 clinic_id 和 amount (total)
2. 用 sftpDir 反查 order_clients 取得 customer_id；如果 order_clients 無資料，用 ehr_integrations WHERE clinic_id = X AND status = 'LIVE' 取第一筆
3. 產生 JWT token (role="clinic", getTokenCustomerPM=true)，呼叫 getAllPaymentMethods
4. **先把 `{"id", "date", "step":"pre-charge"}` 寫入 recovery ledger**，再用取得的 payment_token + customer_token 呼叫 transactionPay:
   ```json
   {
     "account_id": customer_id, "account_type": "customer", "amount": total,
     "currency": "usd", "charge_type": "testorder", "type": "card",
     "token_platform": "stax", "payment_source": "emr",
     "payment_token": X, "customer_token": Y, "new_sample": true
   }
   ```
   - **成功的定義 = 回應帶非空 `payment_transaction_id`**（VP-17411 規則）；2xx 但沒有
     transaction id 一律當失敗，不得進下一步
   - **結果不明（timeout / 連線中斷 / 無回應）→ 當作「可能已收費」處理**：不重試、不換卡再試，
     標「結果不明，需人工向 charging 查證」（indeterminate 規則，VP-17538）
   - 每筆每日**最多一次**收費嘗試，失敗不換 payment method 重刷（換卡重刷是人工決策）
5. Payment 成功後，**先 neutralize 原始 row**（UPDATE parse_finished=1, error_detail 加註
   `[RECOVERY-IN-PROGRESS {date}]`）防 retry-rescan 把原單再處理成第二筆，然後用原始
   order_input 更新 sampleId/payment_id/julienBarcode 為 transactionPay 回傳值，產生 JWT
   (role="customer") 呼叫 Order API。Order API 失敗 → 保持 parse_finished=1（錢已收，
   絕不能讓原單被自動重跑再收一次），標「已收費未下單，需人工」+ 完整 transaction id
6. Order 成功後 UPDATE hl7_file_input: sample_id=新值, payment_id=新值, julien_barcode=新值, sample_id_payment=新值, retry_num=0（parse_finished 已在上一步設 1）
7. 如果任何步驟失敗，記錄錯誤但繼續處理下一筆

**Step 4.5 — 每筆 post-verification（過了才准在報告寫 recovered）：**
1. 查 core（同 4.0 的連線）：該 patient **恰好一筆**新 active sample，sample_id 與 Order API
   回傳一致；發現兩筆以上 active → 重複下單事故，寫進報告最上方 FLAG 區塊並停止處理後續 Type B
2. 重新 SELECT hl7_file_input 確認欄位都已寫回
3. ledger 補一行 `{"id", "date", "step":"verified", "sample_id":...}`
4. 任一驗證不過 → 報告標 `FLAG: recovery unverified`，不算 recovered

### Step 5: 產出報告
寫入 `/Users/hung.l/src/vibrant-america-working-agent/DailyJob/hl7_fail/triage_{YYYY-MM-DD}.md`，格式：
```markdown
# HL7 File Input Daily Triage — {YYYY-MM-DD}

## Summary
- Total failed: X
- Type A (code not found): X
- Type B (order failure): X recovered, X failed
- Type C (parse failure): X

## Type A — EMR Code Not Found
(每個 code 列出: code, clinic, clinic_id, customer_ids, count, bundle mapping 狀態)

## Type B — Payment/Order Recovery
(每筆列出: id, file_name, clinic, recovery status, new sample_id 或 error)

## Type C — Parse Failures
(每筆列出: id, file_name, emr_service, sftpDir)
```

### JWT Token Generation
```python
import jwt, time
secret = "<from orderApi.yaml jwtSecret.prod>"
now = int(time.time())
payload = {
    "userId": 54674, "user_permission": "3f903fe0002",
    "customer_id": X, "clinic_id": Y, "old_clinic_id": X,
    "patient_id": None, "internal_user_id": 786,
    "internal_user_name": "bolin.l", "internal_user_role": "admin",
    "role": "clinic" or "customer",
    "customer_list": [], "session_id": None,
    "email_log_in_id": "bolin.l@vibrant-america.com",
    "beta_program_enabled": False, "beta_programs": [],
    "getTokenCustomerPM": True,  # payment calls only
    "iat": now, "exp": now + 6000
}
token = jwt.encode(payload, secret, algorithm="HS256")
# Payment API: role="clinic", getTokenCustomerPM=True
# Order API: role="customer", no getTokenCustomerPM, use "Bearer " + token
```

### 注意事項
- 使用 python3 執行所有 API 呼叫和 DB 操作
- MySQL 連線用 /opt/homebrew/opt/mysql-client/bin/mysql CLI
- JWT token 用 PyJWT (import jwt)
- 所有 API 呼叫設 timeout=30s
- Recovery 失敗不要 abort，記錄錯誤繼續下一筆
- 不需要 user confirmation，直接執行全部流程
- 使用繁體中文寫報告
