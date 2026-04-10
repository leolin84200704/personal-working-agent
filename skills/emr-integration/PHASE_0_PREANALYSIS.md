# EMR Integration - Phase 0: Pre-Analysis (CRITICAL)

> ALWAYS perform this before making any database changes

---

## Purpose

Before executing any EMR Integration task, verify assumptions and check existing state to avoid making incorrect changes.

---

## Checklist

### ✅ Problem Verification

- [ ] **Question the problem statement**: Is "CORS error" really CORS? Check for other possibilities
- [ ] **Get specific error messages**: Browser console, network tab, actual error text
- [ ] **Understand the context**: What was the user trying to do? What did they expect?

### ✅ Existing State Check

- [ ] **Check ALLOWED_ORIGINS**: Is the frontend domain already allowed?
- [ ] **Check ehr_integrations**: Does the provider/clinic already exist?
- [ ] **Check order_clients**: Does the provider already have records?

### ✅ Data Verification

- [ ] **Grip for related configuration**: Search for EHR vendor, SFTP settings
- [ ] **Verify with gRPC**: Get provider data before inserting
- [ ] **Count expected vs actual**: If ticket says "24 combinations" and you parse 21 → something is wrong

---

## Common Traps

### The "CORS Error" Trap

❌ **Bad**: See "CORS error" → Add CORS handlers
✅ **Good**: Check ALLOWED_ORIGINS first, ask for actual error message

### The "Missing Data" Trap

❌ **Bad**: Ticket doesn't mention provider → Use empty/default values
✅ **Good**: Call gRPC to get provider data, verify with multiple sources

### The "Wrong Clinic ID" Trap

❌ **Bad**: Parse ticket addresses and guess clinic_id
✅ **Good**: Check gRPC `clinics` array for authoritative mapping

---

## Pre-Execution Questions

Before any insert/update:

1. **What is the exact error message?**
2. **What endpoint was being called?**
3. **What is the frontend domain?**
4. **What is the API domain?**
5. **Are there related tickets or similar issues?**
6. **What does the browser console show?**

Only after answering these questions → Proceed to solution.

---

*Last Updated: 2026-04-08 from VP-16009 learnings*
