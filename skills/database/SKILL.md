# Database Operations Skill

> General database operations for EMR integration

---

## Metadata
```yaml
name: database
type: database
agent: emr-integration-agent
priority: high
```

---

## Purpose

Handle database operations for EMR integration:
- Check existing data
- Compare with gRPC data
- Update incorrect records
- Insert new records

---

## Tools Used

See `TOOLS.md` for available database tools:
- `get-existing-data-json` - Fetch existing data
- `update-ehr-integration` - Update ehr_integrations
- `update-order-client` - Update order_clients
- `insert-ehr-integration` - Insert new ehr_integrations
- `insert-order-client` - Insert new order_clients

---

## Critical Rules

1. **Always UPDATE wrong data** - Never skip mismatches
2. **Verify after update** - Always check that data was correctly updated
3. **Use cuid not cuid2** - ID generation must use cuid()

---

*Last Updated: 2026-04-07*
