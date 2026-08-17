---
name: customer-not-found-integrate-playbook
description: hl7_file_input customer_not_found = provider has no ehr_integrations row; fix = mirror practice peer INSERT + bump retry_num; full playbook in emr-order-customer-resolution skill
metadata: 
  node_type: memory
  type: project
  originSessionId: 1cd1f5c7-3cc0-4ed1-8651-aee0a33cb4ca
  modified: 2026-07-23T18:21:11.383Z
---

`hl7_file_input.customer_not_found` (provider name recorded, sample_id null) almost always means the provider has a VA account+NPI but **zero `ehr_integrations` rows** — Leo confirmed (2026-07-23) this will be a recurring case and asked for the procedure to be recorded.

**Fix skeleton** (full playbook in the `emr-order-customer-resolution` skill, "customer_not_found fix playbook" section; worked example: STM HL7FAIL-20260722-MDHQ, precedent VP-16765):
1. Identify provider: `customer_details` (60.3:3307 vibrant_america_information) by name → customer_id + NPI; clinic via `lis_core_v7._clinictocustomer` (A=clinic, B=customer).
2. Find the practice's existing LIVE peer in `ehr_integrations` (match sftp paths/clinic_id) — mirror it column-for-column, changing only identity fields; `msh06 = clinic_id` (2026-04+ convention). FULL_INTEGRATION also needs an `order_clients` row.
3. Transaction + guards (no existing row for customer/NPI, peer state as expected) + dry-run + 100% verify. Write via emr-v2 app account (`^DATABASE_URL=` anchored parse).
4. Re-place the order by `UPDATE hl7_file_input SET retry_num=3` (customer_not_found is retryable post-VP-17120) — the ORIGINAL HL7 file only exists on the owning pod's local disk, so hand-crafting the order is impossible; the retry-rescan (15-min cron) is the only correct re-order path.
5. Owning pod = check `sftp_folder_mapping.pipeline_location` — pod names are ambiguous (on-prem cluster has a deployment named identically to the AKS one: `lis-emr-v2-deployment-prod`).
6. Verify in `lis_core_v7.sample` + `order_info` (ground truth): correct customer+clinic, one active order, no duplicate samples.
