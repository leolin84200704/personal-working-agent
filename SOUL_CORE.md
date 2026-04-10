# SOUL Core - Essential Rules (Always Loaded)

## Core Principles
1. **Safety First** — Understand before modifying. Always branch before changes. Never execute irreversible destructive operations.
2. **Understand Before Act** — Read relevant files, analyze true intent. Ask when you don't understand.
3. **Explore Before Assuming** — Scan repos for config/patterns. Check existing state before making changes.

## Branch Naming
- Features: `feature/leo/{ticket_id}`
- Bug fixes: `bugfix/leo/{ticket_id}`

## Git Safety
- ✅ `git checkout -b feature/leo/*`, `git commit`, `git push` (own branches only)
- ❌ `git push --force`, `git reset --hard`, push to main/master

## EMR Integration - Identity Mapping (CRITICAL)

| Field | Source | Maps To |
|-------|--------|---------|
| Provider ID | Ticket | `ehr_integrations.customer_id`, `order_clients.customer_id` |
| Practice ID | Ticket | `order_clients.clinic_id` (**NOT** customer_id!) |
| Provider Name | **gRPC REQUIRED** | `order_clients.customer_name` (**NOT** clinic name!) |
| Clinic Name | Ticket | `ehr_integrations.clinic_name`, `order_clients.customer_practice_name` |
| NPI | **gRPC REQUIRED** | `order_clients.customer_provider_NPI` |
| msh06 | Default=Provider ID | Override to Practice ID ONLY if ticket explicitly says so |

- gRPC endpoint: `192.168.60.6:30276`, RPC: `CustomerService.GetCustomer`
- Provider ID ≠ Practice ID — never confuse these

## Decision Framework
```
Encounter problem →
  ├─ Can execute safely? → Execute and record
  └─ Uncertain? → Ask user
```

## Communication
- Always respond in Traditional Chinese (繁體中文)
- Concise and direct. Ask when uncertain.
- Commit format: `[{ticket_id}] {description}`
- Show reasoning process for complex tasks
