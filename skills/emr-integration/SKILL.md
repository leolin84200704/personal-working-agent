# EMR Integration Skill

> Core skill for handling EMR Integration tickets (VP-xxxxx series)

---

## Metadata
```yaml
name: emr-integration
type: database
agent: emr-integration-agent
priority: high
```

---

## Purpose

Handle EMR Integration tickets end-to-end:
1. **Phase 0: Pre-Analysis** - Verify assumptions, check existing state
2. Extract Provider ID, Practice ID, Clinic Name
3. Fetch provider personal name and NPI from gRPC
4. Check existing database data
5. Compare and detect mismatches
6. UPDATE existing wrong data (not skip!)
7. Insert new records when needed

---

## Execution Approach (CRITICAL - READ THIS FIRST!)

### NEVER Generate Fake/Test Data

**❌ FORBIDDEN**:
```typescript
// DO NOT DO THIS!
const fakeHL7 = `MSH|^~\\&|TEST|TEST|MDHQ|...`;
PID|1||${sampleId}||FAKE^PATIENT||...
```

**✅ ALWAYS USE REAL DATA SOURCES**:

| Task | Service/Method | Source |
|------|---------------|--------|
| Sample info | `GrpcClientService.getSampleRelevantInfo()` | gRPC |
| Accession | `GrpcClientService.listSample()` | gRPC |
| Test results | `GrpcClientService.getTestResultsDetailedData()` | gRPC |
| Customer info | `GrpcClientService.getCustomer()` | gRPC |
| Patient info | `GrpcClientService.getPatient()` | gRPC |
| PDF report | `GET /lisapi/v1/lis/base-report-service/pdf-cache/download/{accession_id}` | Vibrant API |
| SFTP path | `ehr_integrations.sftp_result_path` | Database query |

### When Task Says "Resend" or "Re-send"

**Definition**: "Resend" means RE-SEND THE EXISTING RESULT, not create a new one.

**Correct Flow**:
1. Find the sample_id in the ticket
2. Call `ResultGenerationService.generateResultHl7ContentReadOnly(sample_id)` OR
   Manually: gRPC getSample → getTestResults → download PDF → generate HL7
3. Send to SFTP path from `ehr_integrations` table (NOT hardcoded `/results/`!)
4. Verify file exists on SFTP server after upload

**NEVER**:
- Generate fake HL7 with fake patient data
- Hardcode SFTP paths (always query DB!)
- Skip verification steps

---

## Phase 0: Pre-Analysis (CRITICAL - ALWAYS DO FIRST)

**⚠️ IMPORTANT: Before any execution, complete this phase!**

### Pre-Execution Checklist

- [ ] **Problem Verification**: Is the stated problem accurate?
- [ ] **Context Gathering**: What exact error? What was the user doing?
- [ ] **Existing State Check**: grep config, check existing data
- [ ] **Data Verification**: Count expected vs actual, verify with gRPC
- [ ] **Existing Clinic Check** (NEW!): Check if clinic already exists
- [ ] **Account Pending Check** (NEW!): Stop if provider_id not assigned

**Common Traps:**

❌ **Bad Pattern**: See "CORS error" → Add CORS handlers
✅ **Good Pattern**: Check ALLOWED_ORIGINS first, question assumptions

❌ **Bad Pattern**: Parse ticket addresses → Guess clinic_id
✅ **Good Pattern**: Check gRPC `clinics` array for authoritative mapping

❌ **Bad Pattern**: Ticket says "Add to existing" → Create new clinic
✅ **Good Pattern**: Search for existing clinic FIRST

❌ **Bad Pattern**: "Account Pending" → Set status=PENDING
✅ **Good Pattern**: "Account Pending" → STOP, cannot proceed

❌ **Bad Pattern**: `"999997" + 1` → `"9999971"` (string concatenation)
✅ **Good Pattern**: `CAST(customer_id AS UNSIGNED) + 1` → `999998` (numeric addition)

**VP-16015 VARCHAR Bug**:
- `customer_id` field is VARCHAR, not INT!
- String concatenation: `"999997" + 1` = `"9999971"` ❌
- Numeric addition: `CAST("999997" AS UNSIGNED) + 1` = `999998` ✅

### NEW: Existing Clinic Detection (CRITICAL)

**When ticket says "Add provider to existing {clinic}"**:

1. **Search for existing clinic**:
```sql
SELECT * FROM ehr_integrations
WHERE clinic_name LIKE '%{clinic_name_from_ticket}%'
   OR sftp_result_path = '/{folder}/results/';
```

2. **If clinic exists**:
   - Use existing `clinic_id`
   - Follow existing `msh06_receiving_facility`
   - Follow existing `hl7_version`
   - Follow existing `ehr_vendor_id`, `sftp_host`, `sftp_port`
   - Add NEW provider to THIS clinic

3. **If clinic doesn't exist**:
   - Proceed with new clinic creation

**Example from VP-16015**:
- Ticket: "Add provider to existing Holistic Health Code"
- Agent created duplicate clinic ❌
- Should have found: customer_id 18235 already exists
- Should have added Brenda Gilmore (NPI: 1851485486) to clinic_id 131492

### NEW: Account Pending Detection

**When ticket says "No Provider ID as it is Account Pending"**:

| Phrase | Meaning | Action |
|--------|---------|--------|
| "Account Pending" | Provider_id not yet assigned | **STOP - Cannot complete** |
| "Provider ID: None" | No provider_id available | **STOP - Cannot complete** |

**What to do**:
1. Do NOT create any records
2. Return to ticket assigner: "Cannot complete - provider_id not yet assigned"
3. Wait for provider_id to be assigned before proceeding

For detailed pre-analysis steps, see: `skills/emr-integration/PHASE_0_PREANALYSIS.md`

---

## Critical Business Rules

### Identity Mapping (DO NOT IGNORE)

| Field | Source | Database Field | Notes |
|-------|--------|----------------|-------|
| **Provider ID** | Ticket description | `customer_id` | The customer/provider account ID |
| **Practice ID** | Ticket description | `clinic_id` | The clinic/facility ID |
| **Practice ID** | Ticket description | `msh06_receiving_facility` | ONLY when ticket says "Practice ID as MSH" |
| **Provider Name** | Ticket description | `contact_name` | Personal name (e.g., "Brenda Gilmore") |
| **Clinic Name** | Ticket description | `clinic_name` | Clinic/facility name (e.g., "Holistic Health Code") |
| **NPI** | RPC call REQUIRED | `customer_npi`, `effective_npi` | Provider's NPI number |

**CRITICAL - VP-16015 Pattern**:
When ticket has BOTH Provider ID and Practice ID:
- Provider ID = `customer_id` (NOT existing clinic's customer_id!)
- Practice ID = `clinic_id`
- If "Practice ID as MSH": Practice ID = `msh06_receiving_facility`

Example VP-16015:
```
Provider ID: 48971    → customer_id = 48971
Practice ID: 131492   → clinic_id = 131492
Practice ID as MSH    → msh06_receiving_facility = 131492
```

**Common Mistake**: Using existing clinic's customer_id instead of ticket's Provider ID!

### Data Storage Rules

**ehr_integrations table:**
- `customer_id` = Provider ID
- `clinic_name` = Clinic Name (from ticket)
- `customer_npi` = NPI (from gRPC)
- `msh06_receiving_facility` = **customer_id by default**, only use Practice ID when ticket explicitly says "MSH value is the Practice ID"

**order_clients table:**
- `customer_id` = Provider ID (from ticket)
- `customer_name` = **Provider Name** (from ticket, e.g., "Brenda Gilmore")
- `customer_practice_name` = Clinic Name (from ticket, e.g., "Holistic Health Code")
- `customer_provider_NPI` = NPI (from gRPC)
- `clinic_id` = Practice ID (from ticket)

### Critical Field Defaults (MUST USE)

**From VP-15874 learnings:**

| Field | Value | Source |
|-------|-------|--------|
| `kit_delivery_option` | `NO_DELIVERY` | Default |
| `status` | `LIVE` | For production (not PENDING) |
| `clinic_name` | Brand name (e.g., "Next Health") | NOT the address! |
| `result_enabled` | `1` (true) | For result integrations |
| `sftp_enabled` | `1` (true) | For active integrations |
| `ehr_vendor_id` | Look up from `ehr_vendor` table | Query by EMR name |
| `sftp_host` | From `ehr_vendor.sftp_host` | After vendor lookup |
| `sftp_port` | From `ehr_vendor.sftp_port` | Not always 22! |
| `report_option` | `PERSONALIZED` | Default |
| `requested_by` | Ticket number (e.g., "VP-15874") | From ticket |
| `last_modified_by` | User name | From context |
| `sftp_result_path` | From `ehr_vendor.sftp_result_path` | Specific path |
| `legacy_emr_service` | Vendor code (e.g., "FOLLOWTHATPATIENT") | From vendor lookup |
| `effective_npi` | NPI from gRPC | Same as customer_npi |
| `customer_npi` | NPI from gRPC | Required! |
| `contact_name` | Leo | Default contact |
| `contact_email` | hung.l@zymebalanz.com | Default contact |

**Vendor Lookup Pattern:**
1. Extract EMR name from ticket (e.g., "Follow That Patient")
2. Query: `SELECT id, sftp_host, sftp_port, sftp_result_path FROM ehr_vendor WHERE name LIKE '%EMR_NAME%'`
3. Use returned values for all vendor-related fields

**SFTP Path Pattern (CRITICAL - from VP-15980):**

When ticket specifies custom SFTP paths (e.g., "results in /asquaredemr/results/, orders in /asquaredemr/orders/"):

| Field | Pattern | Example |
|-------|---------|---------|
| `sftp_result_path` | From ticket | `/asquaredemr/results/` |
| `sftp_ordering_path` | From ticket | `/asquaredemr/orders/` |
| `sftp_archive_path` | `{result_path}archive/` | `/asquaredemr/results/archive/` |

**Rule:** If ticket specifies custom result path, the archive path is `{result_path}archive/` NOT the vendor default `/archive/`

---

## Execution Flow

### Step 1: Analyze Ticket

Extract from ticket description:
- Provider ID (search: "provider id:", "provider id =", "Provider ID:")
- Practice ID (search: "practice id:", "practice id =", "Practice ID:")
- Clinic Name (search: "name:", "clinic:", "Name:")
- EMR Name (search: "emr:", "cerbo", "charm")

**CRITICAL PATTERN DETECTION:**

Check if ticket says MSH value should be Practice ID. Look for:
- "MSH value is the Practice ID"
- "MSH value is the practice ID"
- "msh value is the practice id"
- "update all MSH values to practice ID"
- "use practice ID for MSH"

If ANY of these patterns appear in ticket → **msh06_source = "practice_id"**
Otherwise → **msh06_source = "customer_id"** (default)

### Step 2: Fetch Provider Data (gRPC)

**CRITICAL: Use gRPC for ALL provider-clinic associations!**

Call `get-customer-rpc.ts`:
```bash
npx ts-node scripts/get-customer-rpc.ts --provider-id={provider_id}
```

Extract from response:
- `customer_first_name`
- `customer_last_name`
- `customer_suffix`
- `customer_npi_number`
- **`clinics` array** ← Contains ALL clinic associations for this provider!

**GOTCHA**: The gRPC response includes a `clinics` array with the authoritative clinic_id values:
```json
{
  "customer_id": "43262",
  "customer_first_name": "Anna",
  "customer_last_name": "Emanuel",
  "customer_npi_number": "1073000691",
  "clinics": [
    {"clinic_id": 2930, "clinic_name": "Next Health (West Hollywood)"},
    {"clinic_id": 8003, "clinic_name": "Next Health (Century City)"},
    {"clinic_id": 36290, "clinic_name": "Next Health Studio City"},
    {"clinic_id": 144510, "clinic_name": "Next Health Fashion Island"}
  ]
}
```

**For EACH clinic in the array, create a SEPARATE ehr_integrations record!**

Build `customer_name` = "{first} {last} {suffix}"

**NEVER guess clinic_id from ticket addresses!** Use only the gRPC `clinics` array.

### Step 3: Check Database State

Call `get-existing-data-json.ts`:
```bash
npx ts-node scripts/get-existing-data-json.ts --customer-id={provider_id}
```

Parse JSON response to get:
- `ehr_integrations.customer_npi`
- `order_clients.customer_name`
- `order_clients.customer_provider_NPI`

### Step 4: Compare and Detect Mismatches

Compare existing DB data vs gRPC data:
- `customer_npi` matches gRPC NPI?
- `customer_name` matches "{first} {last} {suffix}"?

**CRITICAL**: If mismatch detected, MUST UPDATE (not skip!)

### Step 5: Execute Database Operations

**MANDATORY VERIFICATION AFTER EVERY OPERATION**:

**After INSERT**:
```bash
# Verify record was created
SELECT * FROM ehr_integrations WHERE customer_id='{provider_id}' LIMIT 1;
SELECT * FROM order_clients WHERE customer_id='{provider_id}' LIMIT 1;
```

**After UPDATE**:
```bash
# Verify record was updated
SELECT customer_npi, msh06_receiving_facility FROM ehr_integrations WHERE customer_id='{provider_id}';
```

**After SFTP Upload**:
```bash
# ALWAYS verify file exists on server
# 1. List the directory
# 2. Find your uploaded file
# 3. Confirm file size matches
```

### Step 5: Execute Database Operations

**If ehr_integrations exists but has wrong NPI:**
```bash
npx ts-node scripts/update-ehr-integration.ts --customer-id={provider_id} --npi={npi}
```

**If order_clients exists but has wrong name/NPI:**
```bash
npx ts-node scripts/update-order-client.ts --customer-id={provider_id} --customer-name="{full_name}" --npi={npi} --clinic-name="{clinic_name}"
```

**If records don't exist:**
```bash
npx ts-node scripts/insert-ehr-integration.ts ...
npx ts-node scripts/insert-order-client.ts ...
```

**⚠️ CRITICAL: Always insert sftp_folder_mapping record!**
After inserting ehr_integrations and order_clients, you MUST also insert sftp_folder_mapping:

```bash
# ONLY for orders (NOT results!)
INSERT INTO sftp_folder_mapping (sftp_source_id, server_folder, local_folder, emrName)
VALUES ({sftp_source_id}, '{server_order_path}', '/MDHQ/Prod/Order/', 'MDHQ');
```

**Example for VP-15980 (Cerbo/MDHQ):**
- sftp_source_id: 3 (MDHQ)
- server_order_path: /asquaredemr/orders/

**Note:** Only insert ORDER mapping, NOT result mapping!

---

## Decision Tree

```
Ticket received
  ├─ Has Provider ID?
  │   ├─ Yes → Call gRPC GetCustomer
  │   └─ No → Ask user for Provider ID
  │
  ├─ Check existing DB data
  │   ├─ ehr_integrations exists?
  │   │   ├─ Yes → Compare NPI
  │   │   │   ├─ Match → Skip
  │   │   │   └─ Mismatch → UPDATE
  │   │   └─ No → INSERT
  │   │
  │   └─ order_clients exists?
  │       ├─ Yes → Compare name and NPI
  │       │   ├─ Match → Skip
  │       │   └─ Mismatch → UPDATE
  │       └─ No → INSERT
```

---

## Output Format

When executing "執行" command, output:

```
🧠 STEP 1: LLM Analysis & Reasoning
============================================================
📝 Reasoning:
   - Extracted Provider ID: 18235
   - Extracted Practice ID: 131492
   - Clinic Name: Holistic Health Code

📋 Missing Data:
   - Provider personal name (need gRPC)
   - NPI (need gRPC)

📞 STEP 2: Fetching Missing Data via gRPC
============================================================
✅ gRPC Response:
   customer_first_name: Megan
   customer_last_name: Tantillo
   customer_suffix: FNP-BC
   customer_npi_number: 1386201606

📊 STEP 3: Checking Database State
============================================================
📊 Existing ehr_integrations:
   customer_npi: 0000000000
   Expected NPI (from gRPC): 1386201606
   ⚠️ MISMATCH! Need to update NPI

🔧 STEP 4: Executing Database Operations
============================================================
--- Updating ehr_integrations (correcting wrong data) ---
✅ Updated 1 row(s)
```

---

## Examples

### VP-15979 (Use customer_id for MSH - DEFAULT)
- Ticket: "Provider ID: 18235, Practice ID: 131492, Name: Holistic Health Code"
- **Ticket does NOT mention** MSH value being Practice ID
- msh06_receiving_facility: **18235** (customer_id - DEFAULT)
- Provider Name from gRPC: "Megan Tantillo FNP-BC"

### VP-15791 (Use practice_id for MSH - EXPLICIT + BULK UPDATE)
- Ticket: "MSH value is the Practice ID for this practice, please add this provider and update **ALL MSH values to practice ID** Name: Foundation Functional Medicine Provider ID: 100212 Practice ID: 127265"
- **Ticket EXPLICITLY says**: "MSH value is the Practice ID" + "update ALL MSH values"
- **This means TWO operations:**
  1. Add new provider (100212) with msh06 = 127265
  2. **BULK UPDATE** all existing providers in clinic 127265 to have msh06 = 127265
- **Tool for bulk update**: `update-clinic-msh.ts --clinic-id=127265`
- This updates ALL records where `clinic_id = 127265` to have `msh06_receiving_facility = 127265`

---

## BULK UPDATE Pattern (CRITICAL)

### When to Use Bulk Update

**Check ticket for these phrases indicating bulk update:**
- "update **ALL** MSH values to practice ID"
- "update all providers in this practice"
- "for **this practice**" + "MSH value is the Practice ID"

**What it means:**
- Not just updating the new provider
- Update **ALL existing providers** in the same clinic/practice
- All records with `clinic_id = {Practice ID}` should have `msh06_receiving_facility = {Practice ID}`

**How to execute:**
```bash
# First, check what records exist
npx ts-node scripts/check-clinic-records.ts
# (Edit script to set the clinic_id)

# Then, bulk update all MSH values
npx ts-node scripts/update-clinic-msh.ts --clinic-id={Practice ID}
```

**Example for VP-15791:**
- Practice ID: 127265
- Found 3 records in clinic:
  - 100212: msh06=127265 ✅ (already correct)
  - 20665: msh06=20665 ❌ (needs update)
  - 20665: msh06=20665 ❌ (needs update)
- After bulk update: all 3 records have msh06=127265 ✅

---

## Multi-Practice Provider Pattern (CRITICAL)

### When Same Provider Appears in Multiple Practices

**Pattern to detect:**
- Ticket contains a table with Practice IDs and Provider IDs
- Same Provider ID appears under multiple Practice IDs
- Example: "Anna Emanuel 43262" appears under Practice 2930, 8003, AND 36290

**What it means:**
- Each (Provider, Practice) combination needs its OWN `ehr_integrations` record
- Same provider will have MULTIPLE records with different `clinic_id` values
- Provider ID 43262 would have:
  - `ehr_integrations` record 1: customer_id=43262, clinic_id=2930, msh06=2930
  - `ehr_integrations` record 2: customer_id=43262, clinic_id=8003, msh06=8003
  - `ehr_integrations` record 3: customer_id=43262, clinic_id=36290, msh06=36290

**Example for VP-15874:**
- 10-13 different practice locations
- 21 total provider-practice combinations
- 19 unique provider IDs (some appear multiple times)
- Same provider (Anna Emanuel 43262) in 3 practices = 3 separate ehr_integrations records

**How to execute:**
1. Parse ALL provider-practice mappings from ticket table
2. Collect unique provider IDs for gRPC batch query
3. For EACH (provider, practice) combination:
   - Create ehr_integrations record with msh06 = Practice ID
   - Create/update order_clients with appropriate clinic_id
4. Same provider = multiple order_clients records with different clinic_id

**Parsing table format:**
```
Practice ID | Location | Provider Name | Provider ID
2930 | West Hollywood | Anna Emanuel | 43262
2930 | West Hollywood | Jeffrey Egler | 26232
8003 | Los Angeles | Anna Emanuel | 43262  ← Same provider!
```



## Multi-Practice Provider Pattern (CRITICAL)

### When Same Provider Appears in Multiple Practices

**Pattern to detect:**
- Ticket contains a table with Practice IDs and Provider IDs
- Same Provider ID appears under multiple Practice IDs
- Example: Same provider name with multiple practice locations

**What it means:**
- Each (Provider, Practice) combination needs its OWN `ehr_integrations` record
- Same provider will have MULTIPLE records with different `clinic_id` values
- Example: Provider 43262 in practices 2930, 8003, 36290 = 3 separate records

**How to handle:**
1. Parse ALL provider-practice mappings from ticket
2. Create ehr_integrations record for EACH combination
3. msh06_receiving_facility = Practice ID for each
4. order_clients.clinic_id = Practice ID for each

---

---

## Resend Result Flow (CRITICAL for "Resend" Tickets)

### When Ticket Says "Resend" or "Re-send"

**❌ BAD Pattern**: Generate fake/test HL7 data
```typescript
// WRONG - this creates fake data!
const hl7 = `MSH|^~\\&|TEST|TEST|MDHQ|${customerId}|${timestamp}...`;
PID|1||${sampleId}||FAKE^PATIENT||...
```

**✅ CORRECT Pattern**: Fetch REAL existing result and re-send

```
1. Use ResultGenerationService.generateResultHl7ContentReadOnly(sample_id)
   - This reads REAL data from gRPC
   - Downloads REAL PDF from Vibrant API
   - Generates COMPLETE HL7 with all test results

2. Or manually follow production flow:
   a. Call gRPC getSampleRelevantInfo(sample_id)
   b. Call gRPC listSample(sample_id) → get accession_id
   c. Call gRPC getTestResultsDetailedData(sample_id)
   d. Download PDF from Vibrant API: GET /lisapi/v1/lis/base-report-service/pdf-cache/download/{accession_id}?style=advanced
      Headers: Authorization: VIBRANT_API_TOKEN
   e. Generate HL7 with real data
   f. Send via SFTP to correct path (from ehr_integrations.sftp_result_path)
```

### VP-15942: File Size Validation (CRITICAL)

**Problem**: Cerbo (MDHQ) has 15MB limit, but Base64 encoding adds ~33% overhead!

| File Size | After Base64 | Status |
|----------|--------------|--------|
| 9MB PDF | 12MB HL7 | ✅ Safe |
| 11.85MB PDF | 15.8MB HL7 | ❌ Exceeds 15MB limit |

**Solution**:
- Compression threshold for Cerbo: **9MB** (not 12MB!)
- Formula: `(15MB / 1.33) * 0.8 = ~9MB`
- Always check: `FileSizeValidationService.getCompressionThreshold(vendorCode)`

**Implementation**:
```typescript
// Get vendor-specific threshold (accounts for Base64 overhead)
const threshold = fileSizeValidationService.getCompressionThreshold('MDHQ'); // ~9MB for Cerbo

// Check if compression needed
if (pdfBuffer.length > threshold || fileSizeValidationService.shouldCompressForVendor(pdfBuffer, 'MDHQ')) {
  pdfBuffer = await adobePdfCompressionService.compressPdf(pdfBuffer, true, 'Cerbo threshold');
}
```

**Verification Steps**:
1. Check HL7 file size < 12MB (80% of 15MB target)
2. Check HL7 file size < 15MB (Cerbo hard limit)
3. Verify SFTP path from `ehr_integrations.sftp_result_path` (NOT just "/results"!)
4. Verify file exists on server after upload

---

*Last Updated: 2026-04-08*
