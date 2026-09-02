# LBS-1762 Jira comment draft (English, NOT posted)

All three requested items are complete.

**1. Report style — already PERSONALIZED (no change needed from us).**
The LIVE integration `cms56tk180041t807p7tt9nxm` (customer 28524 / clinic 127660 / NPI 1245464130, vendor MDHQ/Cerbo) currently has `report_option = PERSONALIZED`. Evidence indicates it was flipped back by a manual DB update after 2026-08-25 (the row's app-managed `updated_at` is untouched and there is no `ehr_integration_notes` entry, so it was not done through the new LIS-7716 PATCH endpoint — presumably IT via the Zendesk 746900 support path). Please confirm on the Zendesk side who performed the flip so the audit trail is complete.

**2. Correct LIVE integration confirmed — no duplicates.**
Only two `ehr_integrations` rows exist for this practice: the LIVE row above and one REJECTED row (`cms3rfrx9000303074l808t7y`, rejected 2026-07-28). There is exactly one LIVE row, and all pushes are bound to it (`result_transmission_records.integration_request_id`), so the push path cannot pick a wrong sibling.

**3. The 17 affected reports have been re-pushed as PERSONALIZED.**
All 17 result_transmission_records rows from 2026-08-04..2026-08-25 (the Classic-era pushes) were re-triggered on 2026-08-27 via `ResultGenerationService/GenerateResultHl7` with `add_report` left to database config, so the re-push exercised the same lookup that future organic pushes will use — confirming the PERSONALIZED setting is effective end-to-end. All 17 new transmission records reached TRANSMITTED status. File names (accessions): 2607166591, 2607086352, 2607166103, 2607136544, 2607166578, 2608046304, 2608036088, 2608046070, 2608036089, 2607216379, 2607306244, 2608066598, 2607176056, 2608136274, 2607146727, 2608076149, 2608176524. Each re-push overwrites the same `{accession}.hl7` file in the practice's SFTP results folder (`/eduardomaristanymdemr/results/`), so Cerbo will ingest the updated PERSONALIZED versions on its next collection cycle.

Root cause context: LIS-7716 (shipped 2026-08-26) fixed the underlying defect — `report_option` was create-only and silently reset to CLASSIC when the integration was re-provisioned on 2026-07-28; re-provisioning now carries the option over, and it is editable post-creation via PATCH `:id/report-option`.
