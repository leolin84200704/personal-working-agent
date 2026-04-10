# Agent Improvement Guide

> Learnings from Claude vs Agent performance gap analysis
> Created: 2026-04-08
> Context: VP-15942, VP-15980, and sample 2501650 result resend

---

## Executive Summary

**Problem**: AI Agent generated fake data and failed to follow proper production flow when asked to "resend" a result.

**Root Cause**: Agent lacked understanding of:
1. What "resend" means in production context
2. How to read existing service code to understand flow
3. The importance of verification at each step
4. That SFTP paths must be queried from database

**Solution**: Updated skills with explicit rules and execution guidelines.

---

## Performance Gap Analysis

### Real-World Example: Sample 2501650 Resend

| Aspect | Claude (Me) | Agent |
|--------|-------------|-------|
| **Understanding "resend"** | Found existing result, used real data | Generated fake HL7 with test data |
| **Code Reading** | Read `ResultGenerationService` to understand flow | Didn't read, guessed the flow |
| **Data Source** | gRPC services, Vibrant API, Database | Hardcoded values |
| **SFTP Path** | Queried `ehr_integrations.sftp_result_path` | Hardcoded `/results/` |
| **Verification** | Listed directory, confirmed file on server | No verification |
| **Output** | 2.60 MB with real PDF, correct path | 918 bytes fake data, wrong path |

---

## Root Causes

### 1. Context Understanding Gap

**What "resend" means**:
- ❌ Agent thought: "Create and send a result"
- ✅ Correct meaning: "Find EXISTING result and send it again"

**Why this happened**:
- Prompt was "resend result sample_id 2501650"
- Agent didn't have context that "resend" = "re-send existing"
- Agent interpreted it as "generate new result"

### 2. Code Reading Gap

**Agent's approach**:
```typescript
// ❌ WRONG - Agent guessed
const hl7 = `MSH|^~\\&|TEST|TEST|MDHQ|${customerId}|${timestamp}...`;
PID|1||${sampleId}||PAUL^MICHAEL||...
```

**Correct approach** (read `ResultGenerationService` first):
```typescript
// ✅ RIGHT - Read service code
const sampleInfo = await grpcService.getSampleRelevantInfo(sampleId);
const testResults = await grpcService.getTestResultsDetailedData(sampleId);
const pdfBuffer = await downloadPdfFromApi(accessionId);  // Real API!
```

### 3. Verification Gap

**What Agent missed**:
- SFTP directory structure is provider-specific (`/rthmemr/results/` not `/results/`)
- File size must account for Base64 encoding overhead
- Need to verify file exists on server after upload

---

## Solutions Implemented

### 1. Updated Skills with Explicit Rules

**File**: `skills/emr-integration/SKILL.md`

Added "Execution Approach" section:
- NEVER Generate Fake/Test Data
- ALWAYS USE REAL DATA SOURCES (listed in table)
- ALWAYS VERIFY OUTPUT (SFTP, database, file sizes)
- QUERY CONFIGURATION, DON'T HARDCODE

### 2. Updated General Skill

**File**: `skills/general/SKILL.md`

Added "CRITICAL EXECUTION RULES":
- READ CODE FIRST, WRITE SECOND
- USE REAL DATA, NEVER FAKE DATA
- ALWAYS VERIFY OUTPUT
- QUERY CONFIGURATION, DON'T HARDCODE
- Understand "RESEND" vs "CREATE NEW"

### 3. Compression Threshold Fix

**File**: `src/modules/result/services/file-size-validation.service.ts`

Changed MDHQ threshold:
- Before: ~9MB (calculated: `(15MB / 1.33) * 0.8`)
- Now: **6MB** (user requested)

**Result**: PDF > 6MB → compress → 2.60 MB HL7 (within 15MB limit)

---

## Best Practices for Agent

### 1. Problem Analysis Phase

**Before writing code**:
```bash
# 1. Find related service files
find src -name "*service*.ts" | grep -i "{domain}"

# 2. Read the service to understand flow
Read("src/modules/{domain}/services/{service}.ts")

# 3. Look for existing methods
grep -r "async.*{action}" src/
```

### 2. Data Source Hierarchy

**Priority order for data sources**:

1. **Database queries** (authoritative)
   - `ehr_integrations.sftp_result_path`
   - `order_clients`, `ehr_integrations`

2. **gRPC services** (real-time data)
   - `getSampleRelevantInfo()`
   - `getTestResultsDetailedData()`
   - `getCustomer()`, `getPatient()`

3. **External APIs** (with auth)
   - Vibrant PDF API: `/lisapi/v1/lis/base-report-service/pdf-cache/download/{accession_id}`

4. **NEVER**: Hardcoded values, fake data

### 3. Mandatory Verification

**After every operation**:

```typescript
// Database operations
console.log(`Verifying: SELECT * FROM ehr_integrations WHERE customer_id='${id}'`);

// SFTP uploads
const list = await sftpConnection.list(remotePath);
const uploaded = list.find(item => item.name === fileName);
console.log(`File verified on server: ${uploaded ? 'YES' : 'NO'}`);
```

---

## Training Checklist

When training agents on EMR Integration tasks, ensure they understand:

- [ ] **"Resend" means re-send existing result, not create new**
- [ ] **Read service code before writing code**
- [ ] **Use gRPC for data, don't generate fake values**
- [ ] **Query database for SFTP paths, don't hardcode**
- [ ] **Verify after every operation**
- [ ] **Check file size limits with Base64 overhead**

---

## Code Examples

### ❌ Wrong Approach (Agent's initial attempt)

```typescript
// Generated fake HL7
const hl7 = `MSH|^~\\&|LIS_EMR|VIBRANT|MDHQ|CERBO|20260408221725||ORU^R01|2501650_20260408221725|P|2.5
PID|1||2501650||PAUL^MICHAEL||19870309|Male|||^^^^^^28080
PV1|1|O
OBX|1|NM|WBC|WBC^White Blood Cell|6.5|K/uL|4.0-11.0||F|||20260408221725||VENDOR
```

**Problems**:
- Fake patient data (PAUL^MICHAEL doesn't match real patient)
- No real test results
- No PDF embedded
- Wrong SFTP path (`/results/` instead of `/rthmemr/results/`)

### ✅ Correct Approach

```typescript
// Get real data from gRPC
const sampleInfo = await grpcService.getSampleRelevantInfo(2501650);
const testResults = await grpcService.getTestResultsDetailedData(2501650);

// Download real PDF from API
const pdfBuffer = await fetch(
  `https://www.vibrant-america.com/lisapi/v1/lis/base-report-service/pdf-cache/download/2602236385?style=advanced&mode=download`,
  { headers: { 'Authorization': VIBRANT_API_TOKEN } }
);

// Query database for SFTP path
const integration = await prisma.ehrIntegration.findFirst({
  where: { customer_id: '28080', legacy_emr_service: 'MDHQ' }
});
const sftpPath = integration.sftp_result_path;  // "/rthmemr/results/"
```

---

## Key Takeaways

1. **Context is everything**: The word "resend" has specific meaning in production
2. **Code > Assumptions**: Always read existing code before implementing
3. **Real data or nothing**: Fake data creates more problems than it solves
4. **Verification is mandatory**: Assumptions about SFTP paths, file sizes, etc. must be verified
5. **User feedback is critical**: Each correction should improve future Agent behavior

---

## Files Modified

### Source Code
- `src/modules/result/services/file-size-validation.service.ts` - 6MB threshold
- `src/modules/result/services/adobe-pdf-compression.service.ts` - Added `shouldCompressForVendor()`
- `src/modules/result/services/result-generation.service.ts` - Force compression for vendors

### Skills
- `skills/emr-integration/SKILL.md` - Added execution rules and resend flow
- `skills/general/SKILL.md` - Added critical execution rules

---

## For Training

When using this document for training:

1. **Explain the performance gap**: Show the table comparison above
2. **Emphasize the rules**: Show the "WRONG vs RIGHT" code examples
3. **Practice verification**: Have agent explain what they will verify before executing
4. **Test with similar task**: Give a "resend" task and check if they follow the new rules

---

## VP-16015: Add Provider to Existing Clinic (NEW 2026-04-09)

### Problem
Ticket asked to "Add provider to existing Cerbo integration" for Holistic Health Code. Agent created a DUPLICATE clinic instead of adding provider to existing one.

### Root Causes

| Issue | What Happened |
|-------|---------------|
| **No existing clinic check** | Agent assumed "Holistic Health Code" was new, didn't check if it exists |
| **"Account Pending" misunderstanding** | Agent set status=PENDING, but actually means "CANNOT PROCEED YET" |
| **Wrong field values** | Used defaults instead of following existing clinic's settings |
| **String concatenation bug** | VARCHAR customer_id treated as string → "999997" + 1 = "9999971" |

### Correct Workflow for "Add Provider to Existing Clinic"

**Step 1: ALWAYS check if clinic exists first**
```sql
SELECT * FROM ehr_integrations
WHERE clinic_name LIKE '%{clinic_name_from_ticket}%'
   OR sftp_result_path = '/{folder}/results/';
```

**Step 2: If clinic exists, use its settings**
```javascript
// For VP-16015, Holistic Health Code (customer_id: 18235) already exists:
{
  clinic_id: 131492,              // Use existing!
  msh06_receiving_facility: "18235",  // Use existing, NOT "MSH"!
  hl7_version: "2.3",             // Use existing, NOT "2.5"!
  ehr_vendor_id: 1,               // From existing
  sftp_host: "34.199.194.51",     // From existing
  sftp_port: 2210,                // From existing
}
```

**Step 3: Understand "Account Pending"**
- "Account Pending" → **STOP**, cannot create integration
- Means no provider_id assigned yet
- Return error: "Cannot complete - provider_id not yet assigned"

### Required Fields (Often Missed)

| Field | Value | Source |
|-------|-------|--------|
| `requested_by` | "VP-16015" | Ticket number |
| `last_modified_by` | "Leo" | User name |
| `ehr_vendor_id` | Lookup from `ehr_vendor` table | `SELECT id FROM ehr_vendor WHERE name LIKE '%Cerbo%'` |
| `clinic_id` | From existing clinic | Don't guess! |
| `hl7_version` | "2.3" for MDHQ | Default from MEMORY |
| `sftp_host` | From `ehr_vendor.sftp_host` | Don't leave null! |
| `sftp_port` | From `ehr_vendor.sftp_port` | Don't leave null! |

### New Rule: Existing Clinic Detection

**When ticket says "Add provider to existing {clinic}"**:
1. Search for clinic by name
2. If found → Note the existing clinic_id and settings
3. READ THE TICKET for Provider ID and Practice ID!
4. Create new record with ticket-specified IDs, not existing customer_id

### CRITICAL: Provider ID vs Practice ID

| Ticket Field | Database Field | Example |
|--------------|----------------|---------|
| Provider ID | `customer_id` | 48971 |
| Practice ID | `clinic_id` | 131492 |
| Practice ID | `msh06_receiving_facility` (if "Practice ID as MSH") | 131492 |

**VP-16015 Mistake**:
- Agent used existing customer_id (18235) instead of ticket's Provider ID (48971)
- Agent used existing msh06 (18235) instead of ticket's Practice ID (131492)

**Correct Action**:
1. Read ticket: Provider ID = 48971, Practice ID = 131492
2. Use Provider ID for customer_id: 48971
3. Use Practice ID for clinic_id: 131492
4. Use Practice ID for msh06 (if specified): 131492
5. Follow existing clinic's other settings (hl7_version, sftp_host, etc.)

---

## Updated Training Checklist

When training agents on EMR Integration tasks, ensure they understand:

- [ ] **ALWAYS check if clinic exists** before creating new
- [ ] **"Account Pending" means STOP** (not status=PENDING)
- [ ] **Follow existing clinic settings** when adding provider to existing clinic
- [ ] **Use CAST(customer_id AS UNSIGNED)** for numeric operations (VARCHAR field!)
- [ ] **Fill ALL required fields**: ehr_vendor_id, clinic_id, sftp_host, sftp_port, requested_by, last_modified_by
- [ ] **"Resend" means re-send existing result, not create new**
- [ ] **Read service code before writing code**
- [ ] **Use gRPC for data, don't generate fake values**
- [ ] **Query database for SFTP paths, don't hardcode**
- [ ] **Verify after every operation**
- [ ] **Check file size limits with Base64 overhead**

---

*Document Owner: Leo (hung.l@zymebalanz.com)*
*Related Tickets: VP-15942, VP-15980, VP-16015*
*Sample ID Reference: 2501650*
*Last Updated: 2026-04-09*
