# VP-18048 — draft Jira comment (English, not posted)

> For Leo to review. Post on VP-18048 once the branch is pushed / PR opened.

---

BE implementation for Internal Notes is ready on `feature/leo/VP-18048` (LIS-transformer-v2). Summary of what it does and the three points that still need a PM answer.

**What ships**

- New column `v2_event.internal_notes` (plain text, nullable) plus `v2_event_exception.updated_internal_notes` so a single occurrence of a recurring appointment can carry its own note, same as `notes` does today.
- GraphQL: `Event.internal_notes` is returned only to clinic (non-patient) tokens. A patient token can still call the same queries and receives `null` for this field; every other field is unchanged.
- Inputs: `internal_notes` added to `createEvent`, `updateEvent`, `createEventByPatient`, `rescheduleClinicalConsult`. A patient token that sends the field is refused.
- Retained through edit (omitting the field leaves it untouched), recurring-series split, and clinician-switch reschedule (cancel-and-rebook copies it to the new event).
- Excluded from the Kafka appointment events that feed downstream notification pipelines. Emails (confirmation, T-15 / 24h reminders, reschedule, update, cancellation), Google / Outlook / Zoom sync already build their payloads field by field and never read this column. There is no `.ics` generation in this service.

**Deploy order**

The column has to exist in `calendar_prod` before the code is deployed (Prisma selects every column on read). Migration script and apply script are in the branch; I will run it against `calendar_dev_new` and `calendar_prod` before the PR is merged.

**Open questions (need PM confirmation)**

1. "Internal user" — implemented as: any non-patient (clinic) token can read and write. No role segmentation among internal users, per PRD non-goal 4. Please confirm.
2. Character limit — implemented as 2000 characters, enforced at the API (not the DB), so it can change without a migration. Please confirm or give the final number.
3. "Editing only this field sends no reschedule email" — not covered by this ticket. Today `updateEvent` sends the update/reschedule notification on every save regardless of which field changed; that behaviour is what PH-822 changes. Until PH-822 ships, saving Internal Notes through the normal edit flow will still trigger the existing update email (the email itself does not contain the notes). If you want a stop-gap that skips notifications when Internal Notes is the only changed field, that is a small follow-up on this ticket — say the word.

**FE contract (VP-18049)**

- Read: select `internal_notes` on any `Event` query. Null means either empty or not permitted.
- Write: pass `internal_notes` (string, ≤ 2000) on the create / update / reschedule inputs. Omit it to leave the stored value untouched; pass `null` to clear.
