# General Problem Solving Skill

> Handles tickets outside of EMR Integration domain

---

## Metadata
```yaml
name: general
type: core
agent: general
priority: medium
```

---

## Purpose

Handle various types of tickets that don't fit into specialized skills:
- Bug reports
- File size issues
- Performance problems
- Configuration issues
- Integration problems (non-EMR)

---

## Problem-Solving Framework

### Step 1: Understand the Problem
- What is the exact error/issue?
- What are the symptoms?
- What is the expected behavior?
- What is the actual behavior?

### Step 2: Gather Context
- When did this start happening?
- What changed recently?
- Who is affected?
- What is the scope?

### Step 3: Investigate
- Check logs/error messages
- Review relevant code
- Check configuration
- Reproduce if possible

### Step 4: Root Cause Analysis
- Identify the root cause
- Understand why it happened
- Check for similar issues

### Step 5: Solution Design
- Propose solution options
- Evaluate trade-offs
- Choose best approach

### Step 6: Implementation
- Make code changes
- Test thoroughly
- Document changes

---

## ⚠️ CRITICAL EXECUTION RULES

### 1. READ CODE FIRST, WRITE SECOND

**Before writing any solution**:
```bash
# Find related service files
find src -name "*service*.ts" | grep -i "{domain_keyword}"

# Read the service to understand the correct flow
Read("src/modules/{domain}/services/{service}.ts")

# Look for existing methods
grep -r "function.*{action}" src/
```

**Example**: For "resend result", first read:
- `src/modules/result/services/result-generation.service.ts`
- Look for `generateResultHl7`, `getSampleRelevantInfo`, etc.

### 2. USE REAL DATA, NEVER FAKE DATA

**❌ FORBIDDEN**:
- Generating fake HL7 with fake patient names
- Hardcoding values like "TEST_PATIENT"
- Making up test results

**✅ REQUIRED**:
- Call gRPC services to get real data
- Query database for existing records
- Download real PDFs from APIs
- Use actual customer/patient IDs from tickets

### 3. ALWAYS VERIFY OUTPUT

**After every operation**:
```bash
# Database operations - verify record created/updated
echo "SELECT * FROM {table} WHERE {id} = '{value}';"

# SFTP uploads - verify file exists on server
# 1. List directory
# 2. Find your file
# 3. Compare file sizes
```

**If verification fails**: STOP, report the error, suggest fix

### 4. QUERY CONFIGURATION, DON'T HARDCODE

**❌ WRONG**:
```typescript
const sftpPath = '/results/';  // Hardcoded!
```

**✅ RIGHT**:
```typescript
const integration = await prisma.ehrIntegration.findFirst({
  where: { customer_id: '28080', legacy_emr_service: 'MDHQ' },
});
const sftpPath = integration.sftp_result_path;  // "/rthmemr/results/" or similar
```

### 5. UNDERSTAND "RESEND" vs "CREATE NEW"

| Term | Meaning |
|------|---------|
| **Resend** | Find EXISTING result, re-send to SAME destination |
| **Create New** | Generate NEW result for a sample (rare) |

**Default assumption**: When ticket says "resend", find existing result first!

---

## Example: VP-15942 (File Size Issue)

### Problem
- Cerbo limit: 15MB
- We sent: 28MB
- Result: Cerbo couldn't process

### Investigation
```bash
# Check compression service
grep -r "ENABLE_ADOBE_PDF_COMPRESSION" .env k8s/

# Check compression threshold
grep -r "compressionThreshold" src/

# Check file size validation
grep -r "file.*size.*limit" src/
```

### Findings
1. Adobe PDF Compression disabled by default
2. Threshold 12MB, Cerbo limit 15MB
3. No validation before sending

### Solution
1. Enable compression
2. Add file size validation
3. Set Cerbo-specific threshold (14MB)

---

## Common Patterns

### File Size Issues
- Check compression settings
- Validate before sending
- Add size limits per vendor
- Implement aggressive compression for large files

### Performance Issues
- Check database queries
- Look for N+1 problems
- Check for missing indexes
- Review caching strategy

### Configuration Issues
- Check environment variables
- Verify k8s configmaps
- Check for typos
- Validate format

### Integration Issues
- Check API endpoints
- Verify authentication
- Check rate limits
- Review error handling

---

## Questions to Ask

When analyzing any problem:

1. **What exactly is broken?** (Be specific)
2. **When did it start?** (Timeline)
3. **What changed?** (Recent changes)
4. **What are the symptoms?** (Observable behavior)
5. **What are the logs saying?** (Error messages)
6. **Can we reproduce it?** (Testing)

---

*Last Updated: 2026-04-08*
