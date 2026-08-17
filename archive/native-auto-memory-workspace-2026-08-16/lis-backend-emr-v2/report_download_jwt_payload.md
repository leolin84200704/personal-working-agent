---
name: report-download-jwt-payload
description: Leo 指定「server 下載 report 並發送到 customer SFTP folder」這條 flow 中，下載 CSV 報告時 JWT 要使用的 payload
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1e4ce2a4-ebf8-4aa2-9a97-5fed4f3f9102
---

**適用範圍（僅限此場景）**:
Server 端在「scheduled report → 下載 CSV → 組 XLSX → 上傳到 customer SFTP folder」這條 flow 中，呼叫 Vibrant API (`${VIBRANT_API_BASE_URL}/result/csvReport?barcode=...`) 時所帶的 JWT。

**已知程式碼位置**:
- 簽 token: `src/modules/scheduled-reports/services/base-report.service.ts` 的 `generateJwtToken()`（目前寫死 userId 54674 / role "ss"，需替換）
- Flow 入口: `generateAndUploadReports()`（同檔案，負責下載 → XLSX → SFTP upload）
- 呼叫者: monthly/weekly/quarterly report services（同目錄）

**要使用的 payload**:
```js
{
  userId: 142346,
  user_permission: null,
  customer_id: null,
  clinic_id: null,
  old_clinic_id: null,
  patient_id: null,
  internal_user_id: 1201,
  internal_user_name: "hung.l",
  internal_user_role: "admin",
  role: "admin",
  customer_list: null,
  session_id: null,
  email_log_in_id: "hung.l@zymebalanz.com",
  beta_program_enabled: false,
  beta_programs: [],
  user_id: 142346,
  user_roles: []
  // iat / exp 由 jwtService.sign({ expiresIn }) 自動產生，不要寫死樣本值
}
```

**Why**: Leo 指定改用自己的 admin 身分（internal_user_id 1201, hung.l, role "admin"）作為呼叫者，取代原本寫死的假 user 54674 / role "ss"。這條 flow 是 server 主動跑 scheduled job，不是 end-user 觸發。

**How to apply**:
- 只套用在上述 SFTP scheduled-reports flow，**不要**套到其他下載 report 場景（例如 end-user 透過 API 下載自己的 report，那些應使用 caller 自己的 JWT）
- 不要把 `iat` / `exp` 寫死，交給 `JwtService.sign()` 依 `expiresIn` 自動填入
- 仍使用 env `JWT_SECRET` 簽發
- 改動前先跟 Leo 確認再 commit
