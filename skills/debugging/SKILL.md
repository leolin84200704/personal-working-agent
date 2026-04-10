# Debugging Skill

> Critical thinking and verification before making changes

---
## Metadata
```yaml
name: debugging
type: core
agent: general
priority: high
```

---

## Purpose

Handle debugging and troubleshooting tasks with critical thinking:
1. Verify the problem statement before assuming solutions
2. Check existing configuration before making changes
3. Test and reproduce issues before coding
4. Use evidence-based analysis instead of pattern matching

---

## Critical Thinking Guidelines

### Rule #1: Never Trust, Always Verify

Before implementing any "fix":
- Check existing configuration (grep, read files)
- Verify the stated problem matches the symptoms
- Test if assumptions are valid

### Rule #2: Question the Problem Statement

When user says "X is broken" or ticket says "CORS error":
- **What exact error do you see?** (browser console, network tab)
- **What were you trying to do?** (action, expected outcome)
- **What did you expect to happen?** (vs. what actually happened)

### Rule #3: Common Traps

**The "CORS Error" Trap:**
- Just because ticket says "CORS error" doesn't mean it is CORS
- Same-origin requests don't have CORS
- Check if domain is in ALLOWED_ORIGINS first
- Ask: Can you share the browser console error?

**The "Missing Data" Trap:**
- Don't assume data is missing from ticket alone
- Check database, check logs, check existing code
- Verify what exists before adding new things

**The "Typo/Bug" Trap:**
- Don't immediately fix what looks like a typo
- Could be configuration issue, environment problem, or usage error
- Get more context before changing code

---

## Execution Flow

### Phase 0: Pre-Analysis (ALWAYS DO THIS FIRST)

```bash
# Step 1: Extract problem statement
problem = extract_from_ticket(ticket)

# Step 2: Critical questions
questions = [
    "What exact error?",
    "What was the user doing?",
    "What was expected?",
    "What actually happened?"
]

# Step 3: Verify with available tools
verification = [
    grep_config("ALLOWED_ORIGINS", "CORS", "API_PREFIX"),
    read_main_file(),
    check_logs(),
    test_endpoint_if_possible()
]
```

### Phase 1: Root Cause Analysis

After pre-analysis, determine:
- Is the problem statement accurate?
- Is it really the stated issue?
- What are other possible causes?

### Phase 2: Solution Design

Only after confirming the root cause:
- Design solution
- Get approval
- Implement
- Test

---

## Tools

### check_config
Search for configuration related to the problem.

### verify_config
Read specific configuration files.

### test_endpoint
Test an API endpoint to see actual behavior.

---

## Examples

### Bad: Pattern Matching without Verification

❌ **Ticket**: "CORS error on VI Personal Settings"
→ **Action**: Add CORS handlers immediately
→ **Result**: Unnecessary changes, doesn't fix real problem

### Good: Critical Thinking with Verification

✅ **Ticket**: "CORS error on VI Personal Settings"
→ **Questions**:
  - "What exact error?" → Need more info
  - "Check ALLOWED_ORIGINS" → Already has www.vibrant-america.com
  - "Context check" → Same-origin request shouldn't have CORS
→ **Action**: Ask for more details, check actual error logs

---

## Key Learning from VP-16009

1. **ALLOWED_ORIGINS** already had the domain
2. Same-origin requests don't trigger CORS
3. "Failed Network Error" is vague - could be many things
4. **Always verify before assuming**

*Last Updated: 2026-04-08*
