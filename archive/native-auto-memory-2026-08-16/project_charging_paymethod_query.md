---
name: charging-paymethod-query
description: "How to check an EMR customer's saved payment methods (diagnose \"no payment method\" order failures) via read-only charging API call"
metadata: 
  node_type: memory
  type: project
  originSessionId: 049b66e8-1245-4c01-8675-f86fbcdc74ed
---

To diagnose `emr_payment_fail_reason: "no payment method"` on emr-v2 HL7 orders: replicate `getFirstPaymentMethod` with a read-only GET to `https://api.vibrant-wellness.com/v1/charging/paymentMethod/allSharedPaymentMethods?customer_id=X&clinic_id=Y`, JWT signed HS256 with `JWT_SECRET_PROD` from `lis-backend-emr-v2/.env` (14-field UserPayload, serializeNulls, userId default 54674, role='clinic', getTokenCustomerPM=true, **no "Bearer " prefix**). Working script: pattern saved in job tmp 2026-07-07, trivially re-creatable from `charge-client.service.ts` + `token-helper.service.ts`.

Resolve customer_id from clinic_id via `lis_emr.ehr_integrations` (Azure MySQL `lisportalprod2`, reachable without VPN as of 2026-07-07).

Verified case 2026-07-07: clinic 5621 / customer 5022 (Randolph Baca, MDHQ) — API returns 200 with both `customer_payment_methods` and `clinic_payment_methods` empty; all 8 customerPay orders 2026-06-17→07-06 (~$2,881) unpaid because the account has no card on file. Related: [[hl7-triage-db-port-blocked]]
