# TOOLS - Available Tools

> This file defines all available tools that skills can use. Tools are interfaces to external systems.

---

## Phase 0: Pre-Analysis (CRITICAL - ALWAYS RUN FIRST)

> **⚠️ IMPORTANT**: Before any execution, Phase 0 MUST verify assumptions!

### Purpose
Phase 0 prevents incorrect changes by:
1. Questioning the problem statement (is it accurate?)
2. Checking existing configuration before making changes
3. Identifying vague or error-prone assumptions

### Automatic Detection
The agent automatically blocks execution when:
- **"CORS error"** without details (ALLOWED_ORIGINS, domain, preflight)
- **"Network error"** without specifics (timeout, status code, DNS)
- **EMR tickets** missing Provider ID or Practice ID

### When Phase 0 Blocks
The agent will:
- Return `can_proceed: false`
- Provide clarifying questions to ask the user
- Suggest verification commands to run

### Example Blocker
```
🚨 PHASE 0 BLOCKER: Vague problem statement detected

Ticket mentions 'CORS error' but lacks verification details.

**Common Trap:** Just because ticket says "CORS error" doesn't mean it is CORS.
- Same-origin requests don't have CORS
- ALLOWED_ORIGINS might already have the domain

**Before proceeding, verify:**
1. What is the EXACT browser console error message?
2. Check ALLOWED_ORIGINS configuration first
```

---

## Code Execution Tools

### read_file
- **Path**: `scripts/read-file.ts`
- **Purpose**: Read a file's contents
- **Usage**: `npx ts-node scripts/read-file.ts --path=src/app.controller.ts`

### write_file
- **Path**: `scripts/write-file.ts`
- **Purpose**: Write content to a new or existing file
- **Usage**: `npx ts-node scripts/write-file.ts --path=file.txt --content=...`

### edit_file
- **Path**: `scripts/edit-file.ts`
- **Purpose**: Edit a file by replacing old_string with new_string
- **Usage**: `npx ts-node scripts/edit-file.ts --path=file.ts --old=old --new=new`

### run_bash
- **Path**: `scripts/run-bash.ts`
- **Purpose**: Execute bash commands
- **Usage**: `npx ts-node scripts/run-bash.ts --command="ls -la"`

---

## Verification Tools (CRITICAL - Use Before Making Changes)

### check_config
- **Purpose**: Search for configuration related to a problem
- **Usage**: `grep -r "ALLOWED_ORIGINS\|CORS\|API_PREFIX" k8s/`
- **Returns**: Lines matching the pattern with file paths

### check_existing_data
- **Path**: `scripts/get-existing-data-json.ts`
- **Purpose**: Check what exists for a provider/clinic in database
- **Usage**: `npx ts-node scripts/get-existing-data-json.ts --customer-id=12345`

### test_api_endpoint
- **Purpose**: Test an API endpoint to see actual behavior
- **Usage**: `curl -X GET 'https://api.example.com/endpoint' -H 'Authorization: Bearer token'`

---

## Git Tools
- **Guardrail**: Only edits within the repository

### run_bash
- **Purpose**: Execute a bash command
- **Usage in execution plan**:
  ```json
  {"action": "run_bash", "params": {"command": "npx ts-node script.ts", "cwd": "/path", "timeout": 120}}
  ```
- **Default timeout**: 120 seconds
- **Default working directory**: Repository root

---

## Database Tools

### get-existing-data-json
- **Path**: `lis-backend-emr-v2/scripts/get-existing-data-json.ts`
- **Purpose**: Fetch existing database data for comparison
- **Usage**:
  ```bash
  npx ts-node scripts/get-existing-data-json.ts --customer-id=12345
  ```
- **Returns**: JSON with `ehr_integrations` and `order_clients` data
- **Fields**: customer_id, customer_npi, clinic_name, status, msh06_receiving_facility, customer_name, customer_provider_NPI, customer_practice_name

### update-ehr-integration
- **Path**: `lis-backend-emr-v2/scripts/update-ehr-integration.ts`
- **Purpose**: Update existing ehr_integrations record (single record)
- **Usage**:
  ```bash
  npx ts-node scripts/update-ehr-integration.ts --customer-id=12345 --npi=1234567890
  ```
- **Updates**: customer_npi, effective_npi

### update-clinic-msh
- **Path**: `lis-backend-emr-v2/scripts/update-clinic-msh.ts`
- **Purpose**: **BULK UPDATE** all MSH values for a clinic to use Practice ID
- **Usage**:
  ```bash
  npx ts-node scripts/update-clinic-msh.ts --clinic-id=127265
  ```
- **Updates**: `msh06_receiving_facility` for ALL records in the clinic
- **Critical**: Use when ticket says "update ALL MSH values to practice ID"

### check-clinic-records
- **Path**: `lis-backend-emr-v2/scripts/check-clinic-records.ts`
- **Purpose**: Check all records for a specific clinic_id
- **Usage**:
  ```bash
  npx ts-node scripts/check-clinic-records.ts
  ```
- **Returns**: Table of all records with their msh06 values

### update-order-client
- **Path**: `lis-backend-emr-v2/scripts/update-order-client.ts`
- **Purpose**: Update existing order_clients record
- **Usage**:
  ```bash
  npx ts-node scripts/update-order-client.ts --customer-id=12345 --customer-name="Name" --npi=1234567890 [--clinic-name="Clinic"]
  ```
- **Updates**: customer_name, customer_provider_NPI, customer_practice_name

### insert-ehr-integration
- **Path**: `lis-backend-emr-v2/scripts/insert-ehr-integration.ts`
- **Purpose**: Insert new ehr_integrations record
- **Usage**:
  ```bash
  npx ts-node scripts/insert-ehr-integration.ts --provider-id=12345 --practice-id=67890 ...
  ```
- **Critical**: Uses cuid (not cuid2) for ID generation

### insert-order-client
- **Path**: `lis-backend-emr-v2/scripts/insert-order-client.ts`
- **Purpose**: Insert new order_clients record
- **Usage**:
  ```bash
  npx ts-node scripts/insert-order-client.ts --customer-id=12345 --customer-firstname="First" --customer-lastname="Last" ...
  ```

---

## gRPC Tools

### get-customer-rpc
- **Path**: `lis-backend-emr-v2/scripts/get-customer-rpc.ts`
- **Purpose**: Fetch provider data from gRPC service
- **Endpoint**: `192.168.60.6:30276`
- **RPC**: `CustomerService.GetCustomer`
- **Usage**:
  ```bash
  npx ts-node scripts/get-customer-rpc.ts --provider-id=12345
  ```
- **Returns**: customer_first_name, customer_last_name, customer_middle_name, customer_suffix, customer_npi_number

---

## Git Tools

### git-create-branch
- **Purpose**: Create feature branch
- **Pattern**: `feature/leo/{ticket_id}` or `bugfix/leo/{ticket_id}`

### git-commit
- **Purpose**: Commit changes
- **Pattern**: `[{ticket_id}] {brief description}`

### git-push
- **Purpose**: Push branch to remote
- **Safety**: Never force push, never push to main

---

## Jira Tools

### jira-get-ticket
- **Purpose**: Fetch ticket details
- **Returns**: key, summary, description, status, attachments

### jira-download-attachment
- **Purpose**: Download ticket attachments

---

*Last Updated: 2026-04-07*
