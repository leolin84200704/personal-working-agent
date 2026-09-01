# DRAFT — Jira comment for VP-18055 (not posted)

Triage complete — every claim in the description verified against prod, plus one additional affected accession found.

**Verified (prod, 2026-09-01):**
- Clinic 139134 (MedSomma Regenerative Wellness) has exactly one ehr_integrations row: `cmsqkuxsn01krxx07cs7g3b4a`, scoped to customer 50554 (Lauren Doyle), FULL_INTEGRATION / LIVE / result_enabled, onprem, `/medsommaemr/results/`. Ordering customers 33765 (Carrie Carda) and 48712 (Shannon Ceglinsky) have no rows.
- Listener behavior confirmed at current main: `findEligibleResultIntegrations` matches the event customer exactly, and the clinic fallback only accepts `customer_id = -1` rows — so every 33765/48712 `report_finished` event is dropped before a job is queued (debug log only).
- All five accessions: finalized in core, orders bound to clinic 139134, zero rows in `result_transmission_records` / `test_order_for_result_integration` / `result_records`. All five are portal-placed orders.
- The delivery path itself works: one result for customer 50554 (sample 2618899) was TRANSMITTED via this integration on 2026-08-19.
- **Reverse audit found a 6th dropped report not in this ticket**: accession `2607306700` (sample 2606528, customer 33765, finalized 2026-08-13 00:45Z — after go-live). Same signature, zero transmission records.

**One correction to the framing:** the row is not a clinic integration stored under the wrong customer — it is a normal provider-level self-service integration (the request flow has no practice-wide option). The actual gap is that no clinic-level catch-all (`customer_id = -1`) row was provisioned for this multi-provider practice.

**Corrective plan (pending approval):**
1. INSERT a clinic-level catch-all row (established VP-16165 / LBS-1656 pattern): `customer_id='-1'`, `clinic_id=139134`, vendor MDHQ, RESULT_ONLY, LIVE, result_enabled, onprem, msh06 `139134`, path `/medsommaemr/results/`, mirroring the existing row's destination so the per-destination dedup prevents double delivery for 50554's own results. Keep the existing provider row untouched (it carries ordering).
2. Re-push all SIX accessions (2607306700, 2607306341, 2608106313, 2607296444, 2608066021, 2606306304) via the result generation service.
3. Post-verify a TRANSMITTED record for each and confirm the files on the vendor SFTP.

**Preventive recommendation:** add an alert (warn + Sentry, per the VP-17544 pattern) when a `report_finished` event finds no eligible integration while a LIVE result-enabled integration exists for the same clinic under a different customer scope — this exact drop would then be visible instead of silent. The auto-integrate practice-wide provisioning question and regression test are proposed as a follow-up ticket since they need a product decision on the request flow.
