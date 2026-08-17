---
name: Execute don't just verify
description: When Leo reports DB errors and asks to fix, actually run UPDATE statements — don't just query and report the values look correct
type: feedback
originSessionId: dd16609b-c6f9-4ecb-9417-f48cb28da8c7
---
When Leo reports DB errors and asks to fix them, **actually execute the UPDATE statements**, then verify.

**Why:** In VP-15955, I queried the DB after Leo's error report and saw "correct" values, then reported "already correct" without executing any UPDATEs. Leo had to send the same request twice. Whether the values appeared correct or not is irrelevant — Leo explicitly asked for fixes, so execute them.

**How to apply:** When the user says "fix these DB values", always:
1. Run the UPDATE statements first (even if values look correct)
2. Show the execution output (rows affected)
3. Then verify with a SELECT
Never skip step 1 by claiming "values are already correct."
