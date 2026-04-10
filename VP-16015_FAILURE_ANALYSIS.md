# VP-16015 Agent Failure Analysis

> Date: 2026-04-09
> Ticket: VP-16015 - Add provider to existing Cerbo integration

---

## Executive Summary

**Result**: Agent created DUPLICATE clinic instead of adding provider to existing clinic.
**Root Cause**: Agent did NOT check if clinic already exists.

**CRITICAL ISSUE**: Ticket says "No Provider ID as it is Account Pending" → **This ticket CANNOT be completed yet!**

---

## What Agent Did Wrong

### 1. Did NOT Check for Existing Clinic

| What Agent Should Do | What Agent Actually Did |
|---------------------|------------------------|
| Check if "Holistic Health Code" exists | Assumed it's a NEW clinic |
| Found customer_id 18235 already exists | Created duplicate customer_id 9999971 → 999998 |
| Follow existing clinic's settings | Used wrong settings |

**Evidence**:
```sql
-- This ALREADY EXISTS:
customer_id: 18235
clinic_name: Holistic Health Code
NPI: 1386201606 (Megan Tantillo FNP-BC)
status: LIVE
```

### 2. Misunderstood "Account Pending"

| Ticket Meaning | Agent Interpretation |
|----------------|---------------------|
| "Account Pending" = Cannot create yet, no provider_id available | "Account Pending" = Set status to PENDING |

**Correct Action**: **DO NOT PROCEED** with this ticket until provider_id is assigned.

### 3. Wrong Field Values (Should Follow Existing Clinic)

| Field | Agent Used | Should Be (from 18235) |
|-------|-----------|----------------------|
| `msh06_receiving_facility` | "MSH" | "18235" (follow existing!) |
| `hl7_version` | "2.5" | "2.3" |
| `ehr_vendor_id` | null | 1 |
| `clinic_id` | null | 131492 |
| `sftp_host` | null | "34.199.194.51" |
| `sftp_port` | null | 2210 |
| `requested_by` | "system" | "VP-16015" |
| `last_modified_by` | null | "Leo" |

### 4. sftp_folder_mapping Issues

| Issue | Description |
|-------|-------------|
| Format | Used "myhhc" instead of proper format |
| Duplicate | Mapping for myhhc may already exist for 18235 |
| Not needed | Should check if mapping exists first |

---

## Correct Workflow for "Add Provider to Existing Clinic"

### Step 1: Check if Clinic Exists
```sql
SELECT * FROM ehr_integrations
WHERE clinic_name LIKE '%Holistic Health Code%'
   OR sftp_result_path = '/myhhc/results/';
```

### Step 2: If Clinic Exists, Check Provider
```sql
SELECT * FROM ehr_integrations
WHERE clinic_id = 131492
  AND customer_npi = '1851485486';  -- Brenda Gilmore's NPI
```

### Step 3: If Provider Doesn't Exist BUT Account is Pending
**STOP** - Cannot create integration without provider_id!

### Step 4: When Provider_id is Assigned
Then create new ehr_integrations record:
- Use EXISTING clinic_id (131492)
- Use EXISTING msh06_receiving_facility ("18235")
- Follow ALL other settings from existing clinic records

---

## Key Learnings for Agent

### 1. ALWAYS Check for Existing Clinic First
```bash
# Before creating ANY integration:
SELECT * FROM ehr_integrations
WHERE clinic_name LIKE '%{clinic_name_from_ticket}%'
   OR sftp_result_path = '/{sftp_folder}/results/';
```

### 2. Understand "Account Pending"
- "Account Pending" = **STOP**, cannot proceed
- This means no provider_id assigned yet
- Return to ticket assigner with: "Cannot complete - provider_id not yet assigned"

### 3. Follow Existing Clinic Settings
When adding provider to EXISTING clinic:
- `clinic_id` = existing clinic's clinic_id
- `msh06_receiving_facility` = existing clinic's value
- `hl7_version` = existing clinic's value
- `ehr_vendor_id` = existing clinic's value
- `sftp_host`, `sftp_port` = existing clinic's values

### 4. Required Fields (from MEMORY)
```javascript
{
  requested_by: "VP-16015",      // Ticket number!
  last_modified_by: "Leo",       // User name
  ehr_vendor_id: 1,              // Lookup from ehr_vendor table
  clinic_id: 131492,             // From existing clinic
  hl7_version: "2.3",            // Default for MDHQ
  sftp_host: "34.199.194.51",    // From ehr_vendor table
  sftp_port: 2210                 // From ehr_vendor table
}
```

### 5. Duplicate Detection
Check by NPI + clinic_id:
```sql
SELECT * FROM ehr_integrations
WHERE customer_npi = '1851485486'
  AND clinic_id = 131492;
```
If exists → ERROR or UPDATE (not duplicate insert!)

---

## VP-16015 CORRECT Execution (After Fix)

### Ticket Fields (CRITICAL - Read These!)

| Field | Value | Database Mapping |
|-------|-------|------------------|
| **Provider ID** | 48971 | → `customer_id` |
| **Practice ID** | 131492 | → `clinic_id` AND `msh06_receiving_facility` |
| **Name** | Holistic Health Code | → `clinic_name` |
| **Provider Name** | Brenda Gilmore | → `contact_name` |
| **NPI** | 1851485486 | → `customer_npi`, `effective_npi` |
| **Practice ID as MSH** | Yes | → `msh06_receiving_facility` = Practice ID |

### Correct Record Created

```sql
customer_id: 48971      -- Provider ID from ticket!
clinic_id: 131492       -- Practice ID from ticket!
msh06_receiving_facility: 131492  -- Practice ID as MSH!
clinic_name: Holistic Health Code
customer_npi: 1851485486
```

### Key Rule

**ALWAYS read ticket carefully for Provider ID and Practice ID!**
- Provider ID → customer_id
- Practice ID → clinic_id AND msh06 (when ticket says "Practice ID as MSH")

---

## VP-16015 Cannot Be Completed (ORIGINAL - Before Provider ID was assigned)

**Reason**: "No Provider ID as it is Account Pending"

**Action Required**:
1. Wait for provider_id to be assigned
2. Then use this provider_id to create integration
3. Link to EXISTING clinic_id (131492)

---

## Files to Update

### AGENT_IMPROVEMENT_GUIDE.md
- Add "Account Pending" handling section
- Add "Existing Clinic" detection workflow
- Add required fields checklist

### MEMORY.md
- Already has correct rules - Agent just needs to FOLLOW them!

### SKILL.md (emr-integration)
- Add Phase 0 pre-analysis step: Check existing clinic
- Add "Account Pending" blocker detection

---

*Analysis by: Leo (hung.l@zymebalanz.com)*
*Date: 2026-04-09*
