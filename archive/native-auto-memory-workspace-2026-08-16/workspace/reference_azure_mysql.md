---
name: Azure MySQL prod credentials
description: Production Azure MySQL connection info for emr_backend database (lisportalprod2)
type: reference
originSessionId: 02a26321-ab4a-4c25-8b9b-e103083f0274
---
Azure MySQL (Production):
- Host: lisportalprod2.mysql.database.azure.com
- Port: 3306
- User: lis_core_emr
- Password: md?At3pUJnS2?Zx68
- SSL: required (mysql client: --ssl-mode=REQUIRED)

Accessible databases for this cred (verified 2026-05-26):
- lis_core_v7  ← patient portal / PNS users live here (table `patient_user`, cols: user_id, username, email_user_id, isActive, ...)
- lis_emr
- emr_backend → ACCESS DENIED for lis_core_emr as of 2026-05-26 (the older "Database: emr_backend" note may be stale or need a different grant). SHOW DATABASES to confirm before assuming.

Patient demographics + address (verified 2026-06-10, via order-intake live test):
- `lis_core_v7.patient` — demographic record. Cols: patient_id, user_id, original_patient_id, patient_first_name, patient_last_name, patient_middle_name, patient_legal_firstname/lastname, patient_birthdate, officeally_id, customer_id. (NOTE: name cols are `patient_first_name`/`patient_last_name`, NOT `first_name`; no email/phone col here.)
- `lis_core_v7.address` — address rows linked by `patient_id` (also customer_id/clinic_id/internal_user_id). Cols: address_id, address_type, street_address, apt_po, city, state, zipcode, country, is_primary_address, ...
- emr-v2's `createPatientV2` gRPC writes both. emr-v2's own `emr_sample` table has NO patient_id; to trace an order→patient, match by name in `lis_core_v7.patient` then join `address` on patient_id. Connect via mysql:// to lis_core_v7 (URL-encode the `?` in the password as %3F).
