# VP-15942 實施報告

> File size too large issue - Cerbo - Accession ID: 2603046143

---

## 執行流程

| 步驟 | 狀態 | 說明 |
|------|------|------|
| 1. Create Branch | ✅ | `bugfix/leo/VP-15942` |
| 2. Analyze | ✅ | 識別根本原因 |
| 3. Write Code | ✅ | 實施 FileSizeValidationService |
| 4. Test | ✅ | 10/10 tests passed |
| 5. Commit | ✅ | Commit 278a11d |
| 6. Report | ✅ | 本文件 |

---

## 問題分析

### 症狀
- Cerbo 收到 28MB 文件
- Cerbo 限制是 15MB
- 文件被拒絕

### 根本原因
1. **Adobe PDF Compression 默認關閉**
   - `ENABLE_ADOBE_PDF_COMPRESSION=false`
2. **沒有文件大小驗證**
   - 發送前不檢查文件大小
3. **Threshold 不適當**
   - 通用 12MB threshold，但 Cerbo 限制 15MB
4. **沒有警告機制**
   - 接近限制時沒有預警

---

## 解決方案

### 1. 新增 FileSizeValidationService

**文件**: `src/modules/result/services/file-size-validation.service.ts`

```typescript
// Vendor file size limits
vendorLimits = {
  'MDHQ': 15,    // Cerbo: 15MB
  'ECW': 20,
  'EPIC': 25,
  'DEFAULT': 20,
}

// Validation method
validateForVendor(buffer, vendorCode, accessionId) {
  const sizeMB = buffer.length / (1024 * 1024);
  const limit = this.getVendorLimit(vendorCode);

  // Warn at 80% of limit
  if (sizeMB > limit * 0.8) {
    // Log warning
  }

  // Reject if exceeds limit
  if (sizeMB > limit) {
    // Log error, return invalid
  }
}
```

### 2. 更新 ResultGenerationService

**修改**: `src/modules/result/services/result-generation.service.ts`

```typescript
// Step 3: Use vendor-specific compression threshold
if (this.fileSizeValidationService.shouldCompressForVendor(pdfBuffer, vendorCode)) {
  pdfBuffer = await this.adobePdfCompressionService.compressPdf(pdfBuffer);
}

// Step 4: Validate file size
const validation = this.fileSizeValidationService.validateForVendor(
  pdfBuffer,
  vendorCode,
  accessionId,
);

if (validation.warning) {
  this.logger.warn(validation.warning);
}

if (!validation.valid) {
  this.logger.error(validation.error);
}
```

### 3. 更新 Module

**修改**: `src/modules/result/result.module.ts`

```typescript
providers: [
  ...
  FileSizeValidationService,  // 新增
],
```

---

## 測試結果

### Unit Tests
```
PASS src/modules/result/services/file-size-validation.service.spec.ts
  FileSizeValidationService - VP-15942
    ✓ should be defined
    ✓ should validate files under Cerbo 15MB limit
    ✓ should warn for files near limit (12MB+)
    ✓ should reject files exceeding limit (16MB)
    ✓ should handle Cerbo alias
    ✓ should handle VP-15942 case (28MB)
    ✓ getCompressionThreshold
    ✓ shouldCompressForVendor
    ✓ should not recommend compression for small files
    ✓ getVendorLimits

Test Suites: 1 passed, 10 passed
```

### TypeScript Compilation
```bash
npx tsc --noEmit
# ✅ No errors
```

---

## Git 資訊

```
Branch: bugfix/leo/VP-15942
Commit: 278a11d
Message: [VP-15942] Add file size validation for Cerbo 15MB limit
Files changed: 5
Lines added: 348
Lines removed: 6
```

---

## 學習要點

### 規則更新 (MEMORY.md)

| 規則 | 值 |
|------|-----|
| Cerbo 文件大小限制 | 15MB |
| 壓縮 Threshold | 12MB (80% of 15MB) |
| 預警 Threshold | 12MB+ (80% of limit) |
| 驗證位置 | 發送前 (getPdfReportBase64) |

### 關鍵實施要點

1. **Vendor-specific limits** - 不同 vendor 有不同限制
2. **Validate before send** - 發送前驗證，不要發送後才知道
3. **Warning mechanism** - 接近限制時預警
4. **Log everything** - 記錄所有驗證結果供監控

---

## 下一步行動

### 立即
- [ ] 合併 branch 到 staging
- [ ] 部署到測試環境
- [ ] 用大文件測試

### 監控
- [ ] 追蹤 Cerbo 文件大小分佈
- [ ] 監控警告日誌
- [ ] 設置告警規則

### 長期
- [ ] 考慮實施激進壓縮策略
- [ ] 考慮文件分割策略
- [ ] 與 Cerbo 討論提高限制可能性

---

*Completed: 2026-04-08*
*Branch: bugfix/leo/VP-15942*
*Status: Ready for merge*
