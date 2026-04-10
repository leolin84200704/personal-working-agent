# VP-15942 分析與解決方案

> File size too large issue - Cerbo - Accession ID: 2603046143

---

## 問題分析

### 問題描述
- **Cerbo 限制**: 15MB 最大文件大小
- **實際發送**: 28MB 文件
- **結果**: Cerbo 無法處理

### 現有代碼分析

**Adobe PDF Compression Service** (`adobe-pdf-compression.service.ts`):
```typescript
// Compression threshold: 12MB
private readonly compressionThresholdBytes: number = 12 * 1024 * 1024;

// But this is DISABLED by default!
this.isEnabled = this.configService.get<string>('ENABLE_ADOBE_PDF_COMPRESSION', 'false') === 'true';
```

**問題**:
1. ❌ Adobe PDF compression **默認關閉**
2. ❌ Threshold 是 12MB，但 Cerbo 限制是 15MB
3. ❌ 即使壓縮，28MB 可能無法壓到 15MB 以下
4. ❌ 沒有文件大小驗證 - 會發送超大文件

---

## 解決方案

### 方案 1: 降低壓縮 Threshold（推薦）

**目標**: 確保所有發送到 Cerbo 的文件都 < 15MB

```typescript
// 在 adobe-pdf-compression.service.ts 中添加 Cerbo 特定處理
private getCerboThreshold(): number {
  return 14 * 1024 * 1024; // 14MB (留 1MB buffer)
}

// 對於 Cerbo 客戶，使用更低的 threshold
shouldCompressForVendor(pdfBuffer: Buffer, vendorCode: string): boolean {
  const threshold = vendorCode === 'MDHQ' 
    ? this.getCerboThreshold()  // 14MB for Cerbo
    : this.compressionThresholdBytes;  // 12MB for others
  
  return pdfBuffer.length > threshold;
}
```

### 方案 2: 文件大小驗證與攔截

**在發送前驗證文件大小**:

```typescript
// 在 sftp-file.service.ts 或 result generation 中添加
async validateFileSizeBeforeSend(
  pdfBuffer: Buffer, 
  vendorCode: string,
  accessionId: string
): Promise<{ valid: boolean; sizeMB: number; error?: string }> {
  const sizeMB = pdfBuffer.length / (1024 * 1024);
  
  // Cerbo has 15MB limit
  const limit = vendorCode === 'MDHQ' ? 15 : 20;  // 20MB default
  
  if (sizeMB > limit) {
    this.logger.error(
      `❌ File ${sizeMB.toFixed(2)}MB exceeds ${vendorCode} limit (${limit}MB). ` +
      `Accession: ${accessionId}`
    );
    
    return {
      valid: false,
      sizeMB,
      error: `File size ${sizeMB.toFixed(2)}MB exceeds ${limit}MB limit`
    };
  }
  
  return { valid: true, sizeMB };
}
```

### 方案 3: 啟用 Adobe PDF Compression for Cerbo

**在環境變量中設置**:
```bash
# .env or k8s config
ENABLE_ADOBE_PDF_COMPRESSION=true  # 目前是 false!
ADOBE_CLIENT_ID=your_client_id
ADOBE_CLIENT_SECRET=your_client_secret
```

### 方案 4: 多層壓縮策略

```typescript
async compressPdfAggressively(pdfBuffer: Buffer): Promise<Buffer> {
  let compressed = pdfBuffer;
  let attempts = 0;
  const maxAttempts = 3;
  
  while (compressed.length > 14 * 1024 * 1024 && attempts < maxAttempts) {
    // First attempt: Adobe HIGH compression
    if (attempts === 0) {
      compressed = await this.adobePdfCompressionService.compressPdf(pdfBuffer);
    }
    // Second attempt: Remove images / optimize
    else if (attempts === 1) {
      compressed = await this.compressPdfRemoveImages(compressed);
    }
    // Third attempt: Split into multiple files
    else {
      throw new Error('File too large even after compression - needs splitting');
    }
    attempts++;
  }
  
  return compressed;
}
```

---

## 推薦實施步驟

### 立即行動 (Hotfix)

1. **啟用 Adobe PDF Compression**
   ```bash
   # Set environment variable
   ENABLE_ADOBE_PDF_COMPRESSION=true
   ```

2. **添加文件大小驗證**
   - 在發送到 Cerbo 前檢查文件大小
   - 如果 > 15MB，記錄錯誤並通知

3. **添加告警**
   - 當文件 > 12MB 時發送告警
   - 通知相關人員

### 長期解決方案

1. **調整壓縮 Threshold**
   - Cerbo: 14MB (留 1MB buffer)
   - 其他: 12MB

2. **實施文件大小驗證**
   - SFTP 發送前驗證
   - HL7 生成時驗證

3. **監控與告警**
   - 追蹤所有發送到 Cerbo 的文件大小
   - 當超過 10MB 時發出預警

---

## 代碼建議

### 新增: File Size Validation Service

```typescript
// file-size-validation.service.ts
@Injectable()
export class FileSizeValidationService {
  private readonly vendorLimits: Record<string, number> = {
    'MDHQ': 15,  // Cerbo: 15MB
    'ECW': 20,
    'EPIC': 25,
  };
  
  validateForVendor(
    buffer: Buffer, 
    vendorCode: string,
    accessionId: string
  ): ValidationResult {
    const sizeMB = buffer.length / (1024 * 1024);
    const limit = this.vendorLimits[vendorCode] || 20;
    
    if (sizeMB > limit) {
      return {
        valid: false,
        sizeMB,
        limitMB: limit,
        error: `File ${sizeMB.toFixed(2)}MB exceeds ${limit}MB limit for ${vendorCode}`
      };
    }
    
    return { valid: true, sizeMB, limitMB: limit };
  }
  
  getWarningThreshold(vendorCode: string): number {
    // Warn at 80% of limit
    const limit = this.vendorLimits[vendorCode] || 20;
    return limit * 0.8;
  }
}
```

---

## 學習要點

### 規則記住

1. **Cerbo 文件大小限制**: 15MB
2. **Adobe PDF Compression 默認關閉** - 需要啟用
3. **需要在發送前驗證文件大小**
4. **不同 vendor 有不同的文件大小限制**

### 更新 MEMORY.md

```markdown
## Cerbo File Size Limit

**From VP-15942**:
- Cerbo maximum file size: 15MB
- Current issue: 28MB file sent
- Solution needed: compress before sending

**Configuration**:
- ENABLE_ADOBE_PDF_COMPRESSION (default: false)
- Threshold: 12MB (should be 14MB for Cerbo)

**Action items**:
1. Enable Adobe PDF Compression
2. Add file size validation before SFTP send
3. Set Cerbo threshold to 14MB (1MB buffer)
```

---

*Created: 2026-04-08*
*Status: Analysis Complete*
*Next: Implement solutions*
