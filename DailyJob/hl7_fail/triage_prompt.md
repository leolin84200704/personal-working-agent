## hl7_file_input Daily Triage

執行以下完整流程，結果輸出到 `/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/` 目錄下，檔名格式 `triage_{YYYY-MM-DD}.md`。

### 連線資訊
- Azure MySQL: host=lisportalprod2.mysql.database.azure.com, port=3306, user=lis_core_emr, password=md?At3pUJnS2?Zx68, db=lis_emr, ssl-mode=REQUIRED
- Order API (prod): POST https://www.vibrant-america.com/lisapi/v1/portal/order/orderTest/order
- Payment Methods: GET https://www.vibrant-america.com/lisapi/v1/charging/paymentMethod/allSharedPaymentMethods
- TransactionPay: POST https://www.vibrant-america.com/lisapi/v1/charging/transaction/pay
- Bundle Mapping: GET https://api.vibrant-wellness.com/v1/pricing/item/promotion/getLegacyBundleMapping?currency=usd
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

### Step 3: Type A 處理 — VACP/Code 分析
1. 呼叫 bundle mapping API，搜尋每個 emr_code_not_found 的 panelId（VACP 後面的數字）
2. 用 sftpDir 反查 order_clients → ehr_integrations 取得 clinic_name, clinic_id, customer_id
3. 記錄：哪些 code 找不到、哪些存在但未分配給該 customer/clinic

### Step 4: Type B 處理 — 手動 Payment + Order Recovery
對每筆 Type B 記錄：
1. 從 order_input JSON 提取 clinic_id 和 amount (total)
2. 用 sftpDir 反查 order_clients 取得 customer_id；如果 order_clients 無資料，用 ehr_integrations WHERE clinic_id = X AND status = 'LIVE' 取第一筆
3. 產生 JWT token (role="clinic", getTokenCustomerPM=true)，呼叫 getAllPaymentMethods
4. 用取得的 payment_token + customer_token 呼叫 transactionPay:
   ```json
   {
     "account_id": customer_id, "account_type": "customer", "amount": total,
     "currency": "usd", "charge_type": "testorder", "type": "card",
     "token_platform": "stax", "payment_source": "emr",
     "payment_token": X, "customer_token": Y, "new_sample": true
   }
   ```
5. Payment 成功後，用原始 order_input 更新 sampleId/payment_id/julienBarcode 為 transactionPay 回傳值，產生 JWT (role="customer") 呼叫 Order API
6. Order 成功後 UPDATE hl7_file_input: parse_finished=1, sample_id=新值, payment_id=新值, julien_barcode=新值, sample_id_payment=新值, retry_num=0
7. 如果任何步驟失敗，記錄錯誤但繼續處理下一筆

### Step 5: 產出報告
寫入 `/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/triage_{YYYY-MM-DD}.md`，格式：
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
