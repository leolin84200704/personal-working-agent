---
name: EMR HL7 encoding is our responsibility
description: Never deflect HL7 encoding issues to "another service" — emr-v2 owns the full pipeline from gRPC to HL7 output
type: feedback
originSessionId: 02a26321-ab4a-4c25-8b9b-e103083f0274
---
HL7 encoding is 100% emr-v2's responsibility. Don't say issues are "not in emr-v2 scope" or "HL7 encoder layer problem" without tracing the full data flow first.

**Why:** Leo corrected this during VP-16270 investigation. I initially said "Total Toxins" missing was an "HL7 encoder layer issue, not in emr-v2 scope" — but emr-v2 IS the HL7 encoder. The correct approach is to trace from gRPC source data through panel mapping to HL7 output to find where data drops.

**How to apply:** For any "missing/wrong data in EMR" investigation, always trace the full chain (gRPC → panel mapping → HL7 output) before making any scope claims. Check the source data first with gRPC, not just the HL7 output.
