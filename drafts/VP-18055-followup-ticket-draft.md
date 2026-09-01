# DRAFT — Follow-up Task ticket for VP-18055 (not created yet)

**Project:** VP
**Type:** Task
**Priority:** P2 - Medium
**Labels:** emr-integration
**Links:** Relates to VP-18055

## Summary

Practice-wide result delivery option for multi-provider practices in the EMR integration flow

## Description

### Background (from VP-18055)

Practice 139134 (MedSomma, Cerbo/MDHQ) integrated via the self-service integration request flow. That flow can only create a provider-level `ehr_integrations` row scoped to the requesting provider's customer_id. The practice has 4 providers sharing one Cerbo instance; results for every provider other than the requester were silently dropped pre-queue for 19 days (6 reports), because result resolution matches either the exact event customer or a clinic-level `customer_id = -1` catch-all row — and nothing in the flow creates the catch-all.

VP-18055 shipped the corrective data fix (manual `-1` row + re-push, done) and a Sentry alert that makes this drop class visible (lis-backend-emr-v2 PR #392, merged). This ticket covers the remaining preventive work: stop the gap from being created in the first place.

### Problem

1. The self-service integration request flow (auto-integrate) has no concept of "integrate the whole practice". A multi-provider practice that self-serves always ends up in the VP-18055 configuration: one provider delivers results, the rest silently depend on someone remembering to add a manual `-1` row.
2. There is no regression coverage for the multi-provider-practice scenario anywhere in the integration provisioning or result resolution flow.

### Proposed scope (needs PM/product confirmation on 1)

1. **Product decision + implementation:** when an integration request is approved/created for a clinic, offer (or default to) practice-wide result delivery — concretely, provision the clinic-level `customer_id = -1` RESULT_ONLY row alongside the provider row (same destination, so the existing per-destination dedup keeps single delivery for the requester). Open questions for PM:
   - Should practice-wide be the default for result delivery, or an explicit checkbox on the request form?
   - Who is authorized to request practice-wide delivery (practice admin role vs any provider)?
   - Does ordering stay provider-scoped (it must today — `-1` rows carry no NPI and never participate in order routing)?
2. **Regression test:** multi-provider practice fixture — provider A integrates, provider B's `report_finished` event must either deliver (if practice-wide) or fire the VP-18055 scope-drop alert (if provider-only).
3. **One-off backfill audit:** scan existing LIVE result-enabled integrations for multi-provider clinics that have no `-1` catch-all row and recent finished samples from non-integrated peers (the VP-18055 signature), and provision/repush where the practice expects clinic-wide delivery.

   A first prod scan (2026-09-01, last 60 days) already ran: 560 dropped-signature samples across 41 clinics / 73 (clinic, provider) pairs. Most are long-standing provider-level configurations (2025 migration rows) whose intent is unknown, but two concrete leads look like real VP-18055 twins:
   - **Clinic 12212 (Sanctuary Functional Medicine, Cerbo/MDHQ):** 8 providers integrated (6 added by VP-16329 on 2026-04-27), but Erin Leffel (customer 48198 — same account batch as the VP-16329 providers) has no row: 7 finalized reports dropped in 60 days.
   - **Clinic 102106:** the only LIVE row is a RESULT_ONLY under a "Practice Admin" account (518714) with `legacy_emr_service` and `sftp_result_path` both NULL — a half-configured integration that can't deliver anywhere; 104 reports from 4 real providers (22066, 34100, 40130, 48365) dropped in 60 days.
   - Clinic 10136 is internal test traffic (999993 / 31889 / 30450), 126 drops — exclude from any remediation and expect it to dominate the new Sentry alert's organic firings.

### Acceptance criteria

- A multi-provider practice completing the integration flow gets result delivery for all its providers without a manual DB insert (per the PM decision in scope item 1).
- Regression test from scope item 2 exists and runs in CI.
- Backfill audit executed and documented; any affected practice fixed or explicitly deferred.
