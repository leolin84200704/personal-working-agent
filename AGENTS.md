# AGENTS - Available Agent Types

> This file defines all available agent types. Each agent specializes in specific tasks.

---

## emr-integration-agent

### Purpose
Handles EMR Integration tickets (VP-xxxxx series). Analyzes tickets, fetches data from gRPC, updates database.

### Capabilities
- Extract provider/practice IDs from ticket description
- Call gRPC GetCustomer RPC for provider name and NPI
- Compare existing database data with gRPC data
- Detect mismatches and UPDATE incorrect data
- Insert new records when needed

### Skills Used
- `emr-integration/analyze` - Analyze ticket and extract data
- `emr-integration/fetch-grpc` - Get provider data from RPC
- `emr-integration/compare` - Compare DB vs gRPC data
- `emr-integration/update` - Update database with correct data
- `emr-integration/insert` - Insert new records

### Business Rules (CRITICAL)
- Provider ID != Practice ID - they are different!
- Provider Name MUST come from gRPC (not ticket)
- msh06_receiving_facility: Use customer_id by default, only use Practice ID when ticket says "MSH value is the Practice ID"
- report_option: Prefer PERSONALIZED when multiple records exist for same clinic_id
- order_clients.clinic_id: Should be Practice ID, not customer_id

---

## code-agent

### Purpose
Handles code modification tickets. Analyzes repos, finds files, makes changes.

### Capabilities
- Scan repos for relevant files
- Read and understand existing code
- Make targeted changes
- Create branches, commit, push

### Skills Used
- `code/analyze` - Analyze ticket and identify repos
- `code/find-files` - Find relevant files
- `code/modify` - Make code changes
- `git/branch` - Create branch
- `git/commit` - Commit changes

---

## scan-agent

### Purpose
Scans Jira for assigned tickets and provides summaries.

### Capabilities
- Fetch assigned tickets from Jira
- Filter by status/priority
- Generate daily summaries

### Skills Used
- `jira/list` - List assigned tickets
- `jira/analyze` - Quick ticket analysis

---

*Last Updated: 2026-04-07*
