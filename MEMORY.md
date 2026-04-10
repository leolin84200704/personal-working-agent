# MEMORY - Knowledge Index

> Agent's accumulated knowledge index. Every memory is learned from actual operations.

---

## Index

- [Repos](#repos) - Each repo's function and architecture
- [Patterns](#patterns) - Common modification patterns
- [Gotchas](#gotchas) - Pitfalls and critical business rules
- [Ticket → Repo Mapping](#ticket--repo-mapping-guide) - Keywords → target repo
- [VP-15874 Learnings](#vp-15874-learnings---critical-field-defaults) - Field defaults, gRPC clinic associations
- [sftp_folder_mapping](#sftp_folder_mapping-rule-corrected) - SFTP mapping rules
- [Field Defaults](#field-defaults-rules-critical) - Default values for DB fields

---

## Repos

### Active Repos (with content)

#### LIS-transformer-v2
- **Purpose**: LIS frontend GraphQL API gateway integrating multiple backend microservices
- **Tech Stack**: NestJS 11, TypeScript, Node.js 20, Prisma (dual databases)
- **Port**: 3390 (GraphQL + REST at `/api`)
- **Key Files**:
  - `src/main.ts` - Bootstrap (port, middleware, Sentry)
  - `src/app.module.ts` - Root module with GraphQL, modules
  - `src/trans/` - Core LIS: orders, patients, settings, merchandise (~4000 lines)
  - `src/calendar/` - Scheduling: Google, Outlook, Zoom integrations
  - `src/questionnaire/` - Surveys and forms
  - `src/setting/` - Provider/clinic settings, 2FA, Twilio phones
  - `src/patientvariable/` - Patient variables for encounter notes
  - `src/role/` - RBAC role management
  - `src/vitals/` - Patient vital signs
  - `prisma/schema.prisma` - Calendar DB (PostgreSQL)
  - `prisma2/schema2.prisma` - Main LIS DB (MySQL)
  - `protos/` - gRPC definitions (25 files)
  - `protos2/` - gRPC definitions v2 (24 files)
- **Databases**:
  - PostgreSQL via `@prisma/client` (Calendar)
  - MySQL via `@prisma/client2` (Main LIS)
- **gRPC Services**: Core LIS, Core Samples V2, Test Results, Shipping, Dashboard, Issue System, Audit Log
- **Infrastructure**: Redis (Azure with Managed Identity), Consul, Kafka, Sentry
- **GraphQL**: Code-first with Apollo Server, JWT context
- **Command**: `npm run start:dev` (run `npx prisma generate` for both schemas first)

#### LIS-transformer
- **Purpose**: NestJS backend service for LIS, REST (port 3190) + gRPC (port 3191)
- **Tech Stack**: NestJS 10, TypeScript, Node.js 16, Prisma
- **Key Files**:
  - `src/main.ts` - Bootstrap (Express on :3190, gRPC on :3191, Swagger at `/api`)
  - `src/trans/` - Core patient data transformation, timelines, tube mapping
  - `src/setting/` - Clinic settings (account, billing, test ordering, PNS)
  - `src/auth/` - JWT + Passport authentication
  - `src/utility/` - CSV processing, Kafka consumers
  - `prisma/schema.prisma` - Primary MySQL DB
  - `prisma/calendar.prisma` - Calendar DB
- **Services**: ~20 downstream microservices via gRPC
- **Kafka**: Dual setup (local/cloud SASL, Azure connection string)
- **PDF**: IronPDF with platform-specific engines
- **Command**: `npm run start:dev`

#### EMR-Backend
- **Purpose**: Java-based EMR order parsing and processing
- **Tech Stack**: Java 8, Maven 3.6.0, MyBatis ORM, gRPC
- **Build**: `mvn package` generates `emr-0.0.1-SNAPSHOT-jar-with-dependencies.jar`
- **Entry Point**: `com.vibrant.emr.EmrOrderTask.ParseOrder`
- **Plugins**:
  - `mybatis-generator` - Generates Mybatis ORM code (`com.vibrant.emr.entity`, `com.vibrant.emr.mapper`)
  - `protobuf` - Generates gRPC code
- **Key**: Run plugins manually before `mvn package`

#### lis-backend-emr-v2
- **Purpose**: Healthcare EMR System Backend with AutoIntegrate functionality
- **Tech Stack**: NestJS, TypeScript, MySQL 8.0, Prisma, Apache Kafka, JWT
- **Port**: 3000, Swagger at `/api/docs`
- **Key Modules**:
  - `ordering/` - Order management
  - `result/` - Lab result management
  - `hl7/` - HL7 encoding/decoding/validation
  - `sftp/` - SFTP connections and file transfers
  - `kafka/` - Event-driven messaging
  - `integration-management/` - AutoIntegrate + Admin Portal
  - `customer-portal/` - Independent customer portal (retransmission, dashboard)
- **Database**: Prisma with MySQL 8.0
- **Command**: `npm run start:dev` (run `npx prisma:generate` first)
- **Approach**: TDD (Test-Driven Development)

#### LIS-setting-consumer
- **Purpose**: Kafka consumer microservice for LIS events, dispatches notifications via Bull/Redis
- **Tech Stack**: NestJS 9.3, TypeScript 4.7, Node.js 16, Prisma (dual schemas)
- **Port**: 6457
- **Architecture**:
  1. Kafka consumers (20+ topics) → Validate & enrich via gRPC
  2. Bull queues (Redis Sentinel) → Async notification jobs
  3. Bull processors → Email, SMS, push notifications
- **Key Files**:
  - `src/setting-consumer/setting-consumer.controller.ts` - Main Kafka consumer (~16K lines!)
  - `src/setting-consumer/bull.consumer.ts` - 20+ Bull processors
  - `prisma/schema.prisma` - Primary MySQL DB
  - `prisma2/schema2.prisma` - Secondary MySQL (transactions/audit)
  - `protos/` - gRPC definitions (23 proto files)
- **Bull Queues**: notify_patient_pay, notify_customer_when_lab_issue, remindScheduleConcierge, pediatric_consent_notification_queue, etc.
- **gRPC Services**: Core LIS, Issue Service, Audit Service
- **Health**: `/health` endpoint + Kafka consumer monitoring cron (every 2 hours)
- **Command**: `npx prisma generate` && `npx prisma generate --schema=prisma2/schema2.prisma` then `npm run start:dev`

#### LIS-backend-v2-coreSamples
- **Purpose**: Core laboratory samples, orders, customers, clinics management
- **Tech Stack**: Go 1.19+, go-micro v4, Ent ORM, MySQL, Redis, Kafka
- **Ports**: gRPC 8084, HTTP 8083
- **Architecture**:
  - `handler/` - HTTP/gRPC request handlers
  - `service/` - Business logic
  - `ent/schema/` - Database schema definitions
  - `publisher/` - Kafka publishers
  - `subscriber/` - Kafka consumers
  - `tasks/` - Asynq background jobs
  - `processor/` - Data transformation
- **Key Services**: OrderService, CustomerService, PatientService, SpecimenService, RequiredTubeVolumeService
- **Infrastructure**: Consul, Redis, Kafka, MySQL, Jaeger (tracing), Sentry
- **Rate Limit**: 100 QPS
- **Command**: `./dev.sh` (requires `make proto` && `make ent` first)
- **Env**: `CORESAMPLES_ENV` (dev, staging, aks_staging, aks_production)

### Empty/Placeholder Repos

These repos appear to be empty or minimal:
- **EHR-backend** - Contains only NestJS template README
- **LIS-backend-billing** - Empty
- **LIS-backend-coreSamples** - Empty
- **LIS-backend-v2-order-management** - Empty
- **Portal-Calendar** - Does not exist

---

## Patterns

### NestJS Projects (LIS-transformer, LIS-transformer-v2, lis-backend-emr-v2, LIS-setting-consumer)
- **Entry Point**: `src/main.ts` for bootstrap, middleware, Sentry
- **Module Structure**: Controllers → Services → DTOs pattern
- **Prisma**: Always run `npx prisma generate` after schema changes
- **Dual Prisma**: Some projects use two schemas (generate both separately)
- **gRPC**: Proto files in `protos/` directory, options in `src/grpc.option.ts`
- **Testing**: Jest with co-located `*.spec.ts` files, E2E in `test/`
- **Docker**: Multi-stage build (node builder → alpine runtime)

### Java/Maven Projects (EMR-Backend)
- **Build**: `mvn package`
- **Plugins**: Run mybatis-generator and protobuf manually before build
- **Entry Point**: Specified in pom.xml, run with `java -cp jar`

### Go Projects (LIS-backend-v2-coreSamples)
- **Code Gen**: `make proto` for protobuf, `make ent` for ORM
- **Testing**: In-memory SQLite via `enttest`, mock Redis with `tempredis`
- **Background Jobs**: Asynq for async tasks

---

## Gotchas

#### TEST_AUTO_LEARNING
- **Problem**: Test problem from VP-15874
- **Solution**: Test solution from VP-15874

#### EMR Integration - Multi-Practice Provider
- **Problem**: The agent failed to identify that a single provider (Anna Emanuel) operates in multiple practice locations and requires distinct `ehr_integrations` records for each. The agent also misread the requirements, claiming the MSH value was not mentioned when the ticket explicitly stated 'MSH used for each practice location should be the Practice ID'.
- **Solution**: 1. Carefully read the ticket description for explicit instructions on unique identifiers (like MSH = Practice ID). 2. When calculating `ehr_integrations` records, identify all provider-practice combinations. If a provider exists at 3 practices, they must have 3 separate records.


### Prisma Dual Schema
- **LIS-transformer-v2**: `prisma/` (PostgreSQL) and `prisma2/` (MySQL) - must generate both
- **LIS-setting-consumer**: `prisma/` (primary) and `prisma2/` (transactions) - must generate both
- Import client2 from custom path: `prisma2/generated/client2`

### Kafka Consumer Groups
- Consumer group IDs must match exactly between config and controller
- Changes to consumer groups affect production message processing
- LIS-setting-consumer has 20+ topics - critical infrastructure

### Large Files
- `LIS-transformer/src/trans/trans.service.ts` ~840KB (~4000 lines)
- `LIS-transformer-v2/src/trans/trans.service.ts` ~4000 lines
- `LIS-setting-consumer/src/setting-consumer/setting-consumer.controller.ts` ~16K lines

### EMR Integration - Provider Name vs Clinic Name (CRITICAL)
- **Ticket description**: Contains clinic/facility name (e.g., "Holistic Health Code")
- **RPC call**: Returns provider personal name (e.g., "Megan Tantillo FNP-BC") + NPI
- **order_clients.customer_name**: MUST be provider personal name from RPC, NOT clinic name
- **order_clients.customer_practice_name**: IS the clinic name from ticket
- **Wrong**: `customer_name = "Holistic Health Code"` ❌
- **Correct**: `customer_name = "Megan Tantillo FNP-BC"` ✅
- **How to fix**: Call `get-customer-rpc.ts` script to get real provider data before inserting
- Read specific line ranges, not entire files

### EMR Integration - MSH Value Detection (CRITICAL)
- **Default**: `msh06_receiving_facility` = customer_id
- **Exception**: When ticket EXPLICITLY says "MSH value is the Practice ID"
- **Pattern to detect**: Look for these phrases in ticket description:
  - "MSH value is the Practice ID"
  - "MSH value is the practice ID"
  - "msh value is the practice id"
  - "update all MSH values to practice ID" ← **This indicates BULK UPDATE!**
  - "use practice ID for MSH"
- **Examples**:
  - VP-15979: No MSH mention → msh06 = 18235 (customer_id) ✅
  - VP-15791: Says "MSH value is the Practice ID" + "update ALL MSH values" → **BULK UPDATE all providers in clinic 127265** ✅
- **Why this matters**: Missing this pattern causes incorrect MSH routing in HL7 messages
- **How to fix**: Check ticket description for MSH patterns FIRST before deciding msh06_source

### EMR Integration - BULK UPDATE Pattern (CRITICAL)
- **When ticket says "update ALL MSH values"**: It means update ALL existing providers in the practice, not just the new one
- **Pattern to detect**: "update **ALL** MSH values to practice ID" or "for **this practice**" + MSH pattern
- **What to do**: Use `update-clinic-msh.ts` to update ALL records with `clinic_id = {Practice ID}`
- **Example VP-15791**:
  - Practice ID: 127265
  - Found 3 records: 100212 (correct), 20665 (wrong), 20665 (wrong)
  - Ran: `npx ts-node scripts/update-clinic-msh.ts --clinic-id=127265`
  - Result: All 3 records now have msh06 = 127265 ✅
- **Why this matters**: Some practices want ALL providers to use the same Practice ID for MSH routing

### EMR Integration - Multi-Practice Provider Pattern (CRITICAL)
- **When ticket has a table with Practice IDs and Provider IDs**: Same provider may appear under multiple practices
- **Pattern to detect**: Table format with columns like "Practice ID", "Location", "Provider Name", "Provider ID"
- **What it means**: Each (Provider, Practice) combination needs its OWN `ehr_integrations` record
- **Example VP-15874**:
  - Anna Emanuel (43262) appears in 3 practices: 2930, 8003, 36290
  - This creates 3 separate ehr_integrations records for the SAME provider
  - Each record has different clinic_id and msh06_receiving_facility
- **Data structure**:
  - `ehr_integrations`: customer_id=43262, clinic_id=2930, msh06=2930
  - `ehr_integrations`: customer_id=43262, clinic_id=8003, msh06=8003
  - `ehr_integrations`: customer_id=43262, clinic_id=36290, msh06=36290
- **Why this matters**: One provider can work at multiple locations; each location needs its own integration record

### TypeScript Strict Mode
- Most projects have `strictNullChecks: false` and `noImplicitAny: false`
- Don't introduce strict typing unless asked

### Environment Variables
- `NODE_ENV` vs `SERVER_ENVIRONMENT` vs `DEPLOY_ENVIRONMENT` vs `platform_type`
- Check which project uses which convention

### EMR Integration Tickets
- **CRITICAL**: EMR integration/order/result tickets should primarily use **lis-backend-emr-v2** (NestJS v2)
- **EMR-Backend** (Java) is the legacy system being migrated FROM
- **Migration path**: EMR-Backend → lis-backend-emr-v2
- For "no results received" or "integration check" tickets:
  1. Check `lis_emr.ehr_integrations` table for practice/customer ID
  2. If no row = no integration (root cause)
  3. Practice ID queries use: `WHERE clinic_id = {ID} AND customer_id = -1`
  4. Customer ID queries use: `WHERE customer_id = {ID}`
- **ALWAYS use existing scripts in lis-backend-emr-v2/scripts/**:
  - `scripts/insert-ehr-integration.ts` - for ehr_integrations table
  - `scripts/insert-order-client.ts` - for order_clients table
- **NEVER write raw SQL directly** - use these scripts instead

### EMR Integration - Auto-Healing Execution

**Agent Auto-Healing Capabilities:**
- **ts-node not found** → Auto-install `npm install --save-dev ts-node`
- **Missing dependencies** → Auto-run `npm install`
- **TypeScript compile errors** → Retry with `--transpile-only` flag
- **Database state checking** → Use `scripts/check-db-state.ts` before updates
- **Smart table updates** → Only update tables that need changes (ehr_integrations, order_clients, sftp_folder_mapping)

**Execution Flow:**
1. Check database state first (is record PENDING or missing?)
2. Use `npx ts-node` instead of `npm run` for direct script execution
3. Auto-heal common errors before giving up
4. Report actions taken (e.g., "Installed ts-node, Used transpile-only mode")

**getCustomer RPC Integration:**
- For real customer data, call gRPC service at `192.168.60.6:30276`
- **Script**: `scripts/get-customer-rpc.ts` - returns JSON with customer data
- Extract: customer_first_name, customer_last_name, customer_middle_name, customer_suffix, customer_npi_number
- **CRITICAL**: Provider personal name (e.g., "Megan Tantillo FNP-BC") comes from RPC, NOT from ticket
- **CRITICAL**: Ticket only contains clinic name (e.g., "Holistic Health Code"), not provider personal name
- Build full provider name: `{first} {middle} {last} {suffix}` → "Megan Tantillo FNP-BC"
- For order_clients: Use `customer_lastname = f"{last} {suffix}"` so `customer_name` becomes "Megan Tantillo FNP-BC"
- Fallback to parsing from ticket description if RPC fails

### EMR Integration - Correct Field Mappings

**ehr_integrations table (via insert-ehr-integration.ts):**
```
Required params:
- customer-firstname, customer-lastname, npi, clinic-name, clinic-id, customer-id, emr-name, folder, ticket-number, integration-type, msh06

Auto-generated/hardcoded:
- id → CUID auto-generated
- ehr_vendor_id → lookup from ehr_vendors table by emr_name
- integration_origin → "NEW_INTEGRATION"
- priority → "NORMAL"
- status → "LIVE"
- contact_name → "Leo"
- contact_email → "hung.l@zymebalanz.com"
- ordering_enabled → 1 if FULL_INTEGRATION/ORDER_ONLY, else 0
- result_enabled → 1 if FULL_INTEGRATION/RESULT_ONLY, else 0
- sftp_enabled → 1
- api_enabled → 1 if ehr_vendor_id=7 (CHARMEHR), else 0
- legacy_result_send_type → HTTP if ehr_vendor_id=7, else SFTP
- hl7_version → "2.3"
- msh06_receiving_facility → msh06 param (required)
- sftp_host/port → lookup from ehr_vendors table
- sftp_result_path → MDHQ: /{folder}/results/, others: copy from existing same emr_name
- sftp_archive_path → MDHQ: /{folder}/results/archive, others: blank
- report_option → lookup existing same clinic_id, else PERSONALIZED
- kit_delivery_option → "NO_DELIVERY"
- legacy_emr_service → from ehr_vendors lookup
- use_vendor_sftp_config → 1

**order_clients table (via insert-order-client.ts):**
```
Required:
- customer-firstname, customer-lastname, npi, clinic-name, clinic-id, emr-name, folder

Key logic:
- Duplicate check: NPI + clinic_id → error if exists
- remote_folder_path: cerbo/mdhq → /{folder}/orders/, others → lookup existing same emr_name or blank
- For MDHQ: also handles sftp_folder_mapping table
```

---

### Vendor Name Mapping
Common names to database codes:
- "cerbo" → "MDHQ"
- "mdhq" → "MDHQ"
- "charm" → "CHARMEHR"
- "eclinical" → "ECW"
- "athena" → "ATHENA"

---

## Ticket → Repo Mapping Guide

| Ticket Keywords | Likely Repo | Module/Path |
|----------------|-------------|-------------|
| calendar, schedule, appointment, Google, Outlook, Zoom | LIS-transformer-v2 | `src/calendar/` |
| GraphQL, patient order, merchandise, PNS, setting | LIS-transformer-v2 | `src/trans/` |
| questionnaire, survey, form | LIS-transformer-v2 | `src/questionnaire/` |
| provider setting, 2FA, Twilio, email branding | LIS-transformer-v2 | `src/setting/` |
| patient variable, encounter note | LIS-transformer-v2 | `src/patientvariable/` |
| role, permission, RBAC | LIS-transformer-v2 | `src/role/` |
| vital sign, BMI | LIS-transformer-v2 | `src/vitals/` |
| HL7, transformation | LIS-transformer | `src/trans/` |
| clinic setting, billing, test ordering | LIS-transformer | `src/setting/` |
| EMR order, AutoIntegrate | lis-backend-emr-v2 | `src/modules/integration-management/` |
| sample, order, patient (core) | LIS-backend-v2-coreSamples | `service/` |
| notification, email, SMS, push | LIS-setting-consumer | `src/setting-consumer/` |
| result ready, shipment, kit, billing | LIS-setting-consumer | Kafka topics |
| Java, gRPC proto | EMR-Backend | `com.vibrant.emr.*` |

---

*Last Updated: 2026-04-09*


---

## VP-15874 Learnings - Critical Field Defaults

**Why**: User corrected multiple field defaults that were incorrect in the initial batch insert.

**Problem**: Agent used wrong default values for several fields when creating ehr_integrations records.

**Solution**:
- **kit_delivery_option**: Default should be `NO_DELIVERY`, not unset
- **status**: Should be `LIVE` for production (not `PENDING`)
- **clinic_name**: Is the clinic/brand name (e.g., "Next Health"), NOT the address
- **result_enabled**: Should be `1` (true) for result integrations
- **sftp_enabled**: Should be `1` (true) for active integrations
- **ehr_vendor_id**: Must be looked up from `ehr_vendor` table based on EMR name
  - Example: "Follow That Patient" → ehr_vendor_id = 44
  - Query: `SELECT id FROM ehr_vendor WHERE name LIKE '%EMR_NAME%'`
- **sftp_host**: Get from `ehr_vendor.sftp_host`
- **sftp_port**: Get from `ehr_vendor.sftp_port` (not always 22)
- **report_option**: Default should be `PERSONALIZED`
- **requested_by**: Should be the ticket number (e.g., "VP-15874")
- **last_modified_by**: Should be the user name (e.g., "Leo")
- **sftp_result_path**: Get from `ehr_vendor.sftp_result_path`
- **legacy_emr_service**: Should be the vendor code/name (e.g., "FOLLOWTHATPATIENT")
- **contact_email**: Don't guess! Use a pattern like `provider-{customer_id}@{domain}.com` or leave placeholder

**effective_npi and customer_npi**:
- MUST be fetched from gRPC service for each provider
- Call `get-customer-rpc.ts` with provider_id to get NPI
- Set both `customer_npi` and `effective_npi` to the same value

**How to apply**: When inserting ehr_integrations records, always:
1. Fetch gRPC data first to get NPI
2. Query ehr_vendor table to get vendor_id, sftp_host, sftp_port, sftp_result_path
3. Use correct defaults for all fields
4. Don't guess contact_email - use pattern or placeholder

*Learned: 2026-04-08 from VP-15874*


---

## Critical Gotcha: Use gRPC for Clinic Associations!

**Why**: VP-15874 had incorrect clinic_id mappings because addresses were guessed from ticket instead of using gRPC.

**Problem**: Agent incorrectly mapped provider-clinic relationships based on addresses in the ticket description, rather than using the authoritative gRPC data.

**Example**:
- Ticket said "12833 Ventura Blvd Suite 161, Los Angeles, CA 91604"
- Agent guessed this was clinic 36290
- But gRPC showed provider 40660 was actually at clinic 144510!

**The 3 Wrong Mappings**:
1. 40660 (Milan Shah): Ticket suggested 36290, gRPC said 144510 ✅
2. 25904 (ROWENA BAYSA): Ticket suggested 144510, gRPC said 27533 ✅
3. 43262 (Anna Emanuel): Missing at clinic 144510 entirely!

**Solution**:
ALWAYS call `get-customer-rpc.ts` and use the `clinics` array from the response:
```json
{
  "customer_id": "43262",
  "clinics": [
    {"clinic_id": 2930, "clinic_name": "Next Health (West Hollywood)"},
    {"clinic_id": 8003, "clinic_name": "Next Health (Century City)"},
    {"clinic_id": 36290, "clinic_name": "Next Health Studio City"},
    {"clinic_id": 144510, "clinic_name": "Next Health Fashion Island"}
  ]
}
```

For each clinic in the array, create a separate ehr_integrations record!

**How to apply**:
1. Call gRPC for each provider_id
2. Extract ALL clinics from the response
3. Create one ehr_integrations record per (provider_id, clinic_id) combination
4. NEVER guess clinic_id from ticket addresses!

*Learned: 2026-04-08 from VP-15874*


---

## VP-15874: Missing Providers from gRPC

**Why**: Original ticket only listed some providers for each clinic. gRPC has the complete list.

**Problem**: When processing VP-15874, initial script only included providers explicitly mentioned in the ticket. But gRPC showed additional providers associated with the same clinics.

**Example - Clinic 36290:**
- Ticket listed: Anna Emanuel (43262)
- gRPC also showed:
  - Darshan Shah (19472) - NPI: 1750446159
  - Jeffrey Egler (25899) - NPI: 1366420523

**Solution**:
For EACH clinic in the ticket, query gRPC for ALL providers at that clinic:
```bash
# For each clinic_id from ticket
npx ts-node scripts/get-all-providers-by-clinic.ts --clinic-id=36290
```

Or more efficiently:
1. Get list of all provider_ids from ticket
2. Call gRPC for each provider
3. Collect ALL (provider_id, clinic_id) combinations from gRPC responses
4. Insert ehr_integrations record for EACH combination

**Key Learning**: The ticket is never the complete source of truth. gRPC has the authoritative provider-clinic mappings.

*Learned: 2026-04-08 from VP-15874*
## VP-15874: Ticket Parsing - Don't Miss Rows!

**Why**: Original script parsed the ticket table but missed some rows.

**Problem**: When VP-15874 ticket has a provider-practice table like:
```
Practice ID | Location              | Provider Name  | Provider ID
36290      | 12833 Ventura Blvd...  | Anna Emanuel  | 43262
36290      | 12833 Ventura Blvd...  | Darshan Shah  | 19472  ← Missed!
36290      | 12833 Ventura Blvd...  | Jeffrey Egler  | 25899  ← Missed!
```

Script must parse ALL rows, not just assume each practice has certain providers.

**Solution**:
1. Parse the entire table from ticket
2. Create one ehr_integrations record per row
3. Verify count matches ticket (e.g., "24 combinations mentioned")

**How to avoid**:
- After parsing, count rows and compare with expected
- If ticket says "24 providers" and you only parsed 21, you missed something!

*Learned: 2026-04-08 from VP-15874*


---

---

## Field Defaults Rules (CRITICAL)

**From VP-15874, VP-15980 learnings:**

| Field | Value | Source |
|-------|-------|--------|
| `report_option` | `PERSONALIZED` | Default (not CLASSIC!) |
| `kit_delivery_option` | `NO_DELIVERY` | Default (not BOTH_BLOOD_AND_NON_BLOOD!) |
| `status` | `LIVE` | For production (not PENDING) |
| `sftp_archive_path` | `{sftp_result_path}archive/` | NOT /archive/! |

### SFTP Path Pattern (VP-15980)

When ticket says "results in /asquaredemr/results/, orders in /asquaredemr/orders/":
- `sftp_result_path`: `/asquaredemr/results/`
- `sftp_ordering_path`: `/asquaredemr/orders/`
- `sftp_archive_path`: `/asquaredemr/results/archive/` ← **result_path + archive/**

**Common Mistake:** Using vendor default `/archive/` instead of custom path.

*Added: 2026-04-08*

---

## Contact Info Defaults (CRITICAL)

**From VP-15980:**

| Field | Value |
|-------|-------|
| `contact_name` | Leo |
| `contact_email` | hung.l@zymebalanz.com |

**Rule:** Always use these defaults for new EMR integrations unless ticket specifies otherwise.

*Added: 2026-04-08*

---

## sftp_folder_mapping Rule (CORRECTED)

**Learned from VP-15980**: ONLY insert ORDER mapping, NOT result mapping!

### Required Tables for New Integration
1. ✅ ehr_integrations
2. ✅ order_clients
3. ✅ **sftp_folder_mapping** (ORDER ONLY!)

### sftp_folder_mapping Pattern
```sql
-- ONLY for orders!
INSERT INTO sftp_folder_mapping (sftp_source_id, server_folder, local_folder, emrName)
VALUES (3, '/asquaredemr/orders/', '/MDHQ/Prod/Order/', 'MDHQ');
```

**DO NOT insert result mapping!**

### Key Fields
- sftp_source_id: Get from emrSftpSource table (e.g., MDHQ = 3)
- server_folder: The SFTP order path from ticket (e.g., /asquaredemr/orders/)
- local_folder: /MDHQ/Prod/Order/
- emrName: MDHQ

*Corrected: 2026-04-08*

---

## File Size Issue - Cerbo (VP-15942)

**Problem**: Cerbo has 15MB file size limit, we sent 28MB file

**Root Causes**:
1. Adobe PDF Compression is DISABLED by default (ENABLE_ADOBE_PDF_COMPRESSION=false)
2. Compression threshold is 12MB, but Cerbo limit is 15MB
3. No file size validation before SFTP send
4. Even with compression, 28MB may not compress below 15MB

**Solutions**:
1. Enable Adobe PDF Compression: `ENABLE_ADOBE_PDF_COMPRESSION=true`
2. Lower threshold for Cerbo: 14MB (1MB buffer)
3. Add file size validation before sending
4. Implement aggressive compression for files > 10MB

**Vendor File Size Limits**:
| Vendor | Limit | Threshold (with buffer) |
|--------|-------|-------------------------|
| Cerbo (MDHQ) | 15MB | 14MB |
| ECW | 20MB | 18MB |
| Epic | 25MB | 23MB |

**Files to Check**:
- `src/modules/result/services/adobe-pdf-compression.service.ts`
- `src/modules/result/services/result-generation.service.ts`
- `src/modules/sftp/services/sftp-file.service.ts`

*Added: 2026-04-08*
