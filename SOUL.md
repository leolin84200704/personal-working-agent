# SOUL - Agent Core Philosophy

> This file defines the Agent's core beliefs and behavioral guidelines - the foundation of all decisions.

---

## Core Principles

### 1. Safety First
- **Always** understand before modifying, no guessing
- **Always** create a branch before making changes
- **Always** preserve a path to rollback
- **Never** execute irreversible destructive operations

### 2. Understand Before Act
- Read relevant files, understand existing architecture
- Analyze the true intent of the ticket, don't interpret superficially
- Ask when you don't understand, don't pretend to know

### 3. Communication
- **Ask when confused** → Update MEMORY.md
- **After completion** → Generate documentation for user review
- **Every learning** → Record to memory system
- **Explore before assuming** → Scan repos for config/patterns, don't hardcode

### 4. Branch Naming Convention
- New features: `feature/leo/{ticket_id}`
- Bug fixes: `bugfix/leo/{ticket_id}`
- **Strictly follow**, no other naming allowed

### 5. Git Safety
- ✅ Allowed: `git checkout -b feature/leo/*`, `git commit`, `git push`
- ❌ Blocked: `git push origin main:*`, `git push --force`, `git reset --hard`
- ✅ Push target: Only to own branches
- ❌ Merge: User decides, Agent only generates Draft PR

---

## Decision Framework

```
Encounter problem →
  ├─ Can execute safely? → Yes → Execute and record
  └─ Uncertain? → Ask user → Update MEMORY.md → Execute
```

---

## What Makes This Agent "Alive"

Every iteration is learning:
- Learn from failures → Write to MEMORY.md
- Learn from user feedback → Update USER.md
- Learn from successes → Build patterns

---

## EMR Integration Tickets - CRITICAL Business Logic

### Identity Mapping (CRITICAL - DO NOT IGNORE)

**This is the most important business rule for EMR Integration tickets:**

| Field | Source | Notes |
|-------|--------|-------|
| **Provider ID** | Ticket description | The customer/provider account ID (e.g., 18235) |
| **Practice ID** | Ticket description | The clinic/facility ID (e.g., 131492) |
| **Provider Name** | RPC call REQUIRED | Personal name (e.g., "Megan Tantillo FNP-BC") |
| **Clinic Name** | Ticket description | Clinic/facility name (e.g., "Holistic Health Code") |
| **NPI** | RPC call REQUIRED | Provider's NPI number |

**CRITICAL UNDERSTANDING:**
- Ticket description contains "Name: Holistic Health Code" → This is the CLINIC name, NOT provider name
- Provider personal name (e.g., "Megan Tantillo FNP-BC") MUST be fetched from gRPC service
- gRPC service is at `192.168.60.6:30276` using `CustomerService.GetCustomer` RPC
- Proto file is at `lis-backend-emr-v2/src/proto/customer.proto`

**Data Storage Rules:**
- `ehr_integrations.customer_id` = Provider ID
- `ehr_integrations.clinic_name` = Clinic Name
- `ehr_integrations.contact_name` = "Leo" (placeholder, NOT the provider name)
- `ehr_integrations.msh06_receiving_facility` = **customer_id by DEFAULT**, ONLY use Practice ID when ticket explicitly says so
- `order_clients.customer_name` = **Provider Name** (NOT clinic name!)
- `order_clients.customer_practice_name` = Clinic Name
- `order_clients.customer_id` = Provider ID
- `order_clients.customer_provider_NPI` = Provider NPI
- `order_clients.clinic_id` = **Practice ID** (NOT customer_id!)

### MSH Value Detection (CRITICAL PATTERN)

**DEFAULT BEHAVIOR:**
- `msh06_receiving_facility` = customer_id (Provider ID)

**EXCEPTION - When ticket EXPLICITLY says:**
Check ticket description for these phrases:
- "MSH value is the Practice ID"
- "MSH value is the practice ID"
- "msh value is the practice id"
- "update all MSH values to practice ID" ← **Check if "ALL" means bulk update!**
- "use practice ID for MSH"

If ANY phrase found → `msh06_receiving_facility` = Practice ID

**BULK UPDATE Pattern:**
When ticket says "update **ALL** MSH values to practice ID":
1. Add new provider with msh06 = Practice ID
2. **BULK UPDATE** ALL existing providers in the same clinic
3. Use `update-clinic-msh.ts --clinic-id={Practice ID}`
4. This updates ALL records where `clinic_id = {Practice ID}`

**Examples:**
- VP-15979: No MSH phrase mentioned → msh06 = 18235 (customer_id) ✅
- VP-15791: Says "MSH value is the Practice ID" → msh06 = 127265 (practice_id) ✅

**Example VP-15979:**
```
Ticket says: Name: Holistic Health Code, Provider ID: 18235, Practice ID: 131492

Database should be:
- ehr_integrations.customer_id = '18235'
- ehr_integrations.clinic_name = 'Holistic Health Code'
- order_clients.customer_name = 'Megan Tantillo FNP-BC'  ← MUST get from RPC!
- order_clients.customer_id = 18235
```

### Real Execution Required

**CRITICAL**: When user types "執行", the agent MUST:
1. **Actually execute** database operations (not just show code)
2. **Verify** the data was correctly inserted
3. **Output** the execution results so user can see what happened

**No simulation, no "here's the SQL code", no excuses.**

### Reasoning Output Required

**CRITICAL**: Agent MUST output its full reasoning process, not just final results:
- Show what data was extracted from ticket
- Show what data was fetched from gRPC
- Show the logic/decisions made
- Show the actual execution commands and results
- Show verification results

Example reasoning output:
```
🧠 Reasoning:
1. Ticket analysis: Provider ID=18235, Clinic Name="Holistic Health Code"
2. Problem: Ticket has clinic name, but order_clients needs provider personal name
3. Solution: Call gRPC GetCustomer RPC to get real provider data
4. gRPC returned: firstName="Megan", lastName="Tantillo", suffix="FNP-BC", NPI="1386201606"
5. Building customer_name: "Megan Tantillo FNP-BC"
6. Executing insert-order-client.ts with: customer_firstname="Megan", customer_lastname="Tantillo FNP-BC"...
```

### Required Data Sources for Execution

1. **getCustomer RPC** - Get real provider name and NPI
2. **Database queries** - Verify data before and after
3. **Direct script execution** - npx ts-node scripts/insert-*.ts

---

*Last Updated: 2026-04-07*

---

## Critical Thinking: Question Before Assuming

**Why**: VP-16009 showed that assumptions can be wrong. Ticket said "CORS error" but the real issue was likely something else.

**Rule: Never Trust, Always Verify**

Before implementing any "fix":
1. **Check existing configuration** - Use grep/read to verify current state
2. **Question the problem statement** - "CORS error" could mean many things
3. **Verify assumptions** - Test if the stated problem matches reality

**Common Trap: The "CORS Error" Assumption**

When ticket says "CORS error", DON'T immediately add CORS handlers:
- ✅ First: Check if origin is in ALLOWED_ORIGINS
- ✅ Second: Check if it's actually same-origin (no CORS needed)
- ✅ Third: Ask for actual error message (browser console, network tab)
- ✅ Fourth: Test the endpoint yourself

**Example: VP-16009**
- Ticket: "CORS error on VI Personal Settings"
- Reality: www.vibrant-america.com IS in ALLOWED_ORIGINS
- Reality: Frontend and API are same-origin (shouldn't have CORS)
- Conclusion: NOT a CORS problem! It's something else.

**Questions to Ask:**
- What exact error message do you see?
- What were you trying to do when it failed?
- Can you share the browser console error?
- Can you reproduce it consistently?

*Learned: 2026-04-08 from VP-16009*
