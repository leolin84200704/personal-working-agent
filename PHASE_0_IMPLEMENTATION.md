# Phase 0 Pre-Analysis Implementation

> Critical thinking capability for the AI agent

---

## What Was Implemented

### 1. Phase 0 Pre-Analysis Workflow
Added `_phase_0_pre_analysis()` method to `MarkdownExecutor` that:
- Runs BEFORE any ticket execution
- Detects vague/problematic problem statements
- Blocks execution when clarification is needed
- Provides specific questions to ask the user

### 2. Critical Pattern Detection
The agent now automatically detects:
- **Vague CORS errors**: "CORS error" without ALLOWED_ORIGINS/domain details
- **Vague network errors**: "Network error" without timeout/status code
- **Missing identifiers**: EMR tickets without Provider/Practice IDs

### 3. Integration Points
- `execute_emr_integration()`: Now runs Phase 0 before analysis
- `_llm_analyze_with_skill()`: Receives Phase 0 results to inform planning
- `_execute_plan()`: Gets Phase 0 context for execution

---

## How It Works

```
Ticket Received
       ↓
┌─────────────────────────────────────────┐
│  PHASE 0: Pre-Analysis (CRITICAL)       │
│  - Question problem statement           │
│  - Check existing configuration         │
│  - Detect vague assumptions             │
└─────────────────────────────────────────┘
       ↓
    Can Proceed?
       ↓
    NO ──→ Return clarifying questions
       ↓
    YES
       ↓
┌─────────────────────────────────────────┐
│  LLM Analysis with Phase 0 Context      │
│  - Incorporate verified assumptions     │
│  - Create execution plan                │
└─────────────────────────────────────────┘
       ↓
┌─────────────────────────────────────────┐
│  Execute Plan                           │
└─────────────────────────────────────────┘
```

---

## Test Results

All 5 Phase 0 tests pass:

```
TEST 1: Vague CORS Error → ✅ BLOCKED
TEST 2: Vague Network Error → ✅ BLOCKED
TEST 3: EMR Missing IDs → ✅ BLOCKED
TEST 4: Complete EMR Ticket → ✅ PASSED
TEST 5: CORS with Details → ✅ PASSED
```

Run tests: `python3 /Users/hung.l/src/lis-code-agent/test_phase_0.py`

---

## What This Solves

### VP-16009 Example
**Before**: Agent sees "CORS error" → Adds OPTIONS handlers blindly

**Now**: Agent sees "CORS error" → Blocks and asks:
1. What is the EXACT browser console error?
2. Is the frontend domain in ALLOWED_ORIGINS?
3. Is this same-origin or cross-origin?

### Root Cause
The agent (like humans) suffered from **pattern-matching without verification**:
- See "CORS" → Think CORS solution
- See "network error" → Think network fix
- **Missing**: Step back and verify the problem statement first

---

## Files Modified

| File | Changes |
|------|---------|
| `src/core/markdown_executor.py` | Added `_phase_0_pre_analysis()` method, updated `execute_emr_integration()` to call Phase 0 first |
| `TOOLS.md` | Added Phase 0 documentation section |
| `skills/debugging/SKILL.md` | Created debugging skill with critical thinking guidelines |
| `skills/emr-integration/PHASE_0_PREANALYSIS.md` | Created Phase 0 reference for EMR tickets |
| `skills/emr-integration/SKILL.md` | Added Phase 0 section to execution flow |

---

## Next Steps

### Immediate
1. **Test with real ticket**: Run agent on VP-16009 to verify Phase 0 triggers correctly
2. **Get user answers**: Use clarifying questions to get actual error details
3. **Verify root cause**: Use suggested commands (grep ALLOWED_ORIGINS, test endpoint)

### Future Enhancements
- Add more pattern detectors (authentication errors, database issues)
- Integrate with actual config reading (not just bash commands)
- Auto-run verification commands when safe
- Learn from blocked tickets to improve detection

---

## Key Insight

**Critical Thinking = Verification Before Execution**

The agent now follows the same workflow a skilled engineer would:
1. Don't trust the problem statement blindly
2. Check existing state before changing things
3. Ask questions when information is incomplete
4. Only proceed when assumptions are verified

This prevents the "fix first, understand later" anti-pattern that caused issues like VP-16009.

---

*Implemented: 2026-04-08*
*Inspired by: VP-16009 learnings*
