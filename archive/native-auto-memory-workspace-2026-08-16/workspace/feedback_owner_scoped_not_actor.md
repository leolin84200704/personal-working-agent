---
name: feedback_owner_scoped_not_actor
description: "Resolve per-owner attributes (timezone/settings/perms) from the RESOURCE OWNER's ids, not the acting user's JWT ids"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 25da76b7-c932-4728-aedf-05b96b1a128c
---

When resolving an owner-scoped attribute for a resource (e.g. a calendar/event's timezone, settings, preferences), key the lookup off the **resource owner's** ids — for a v2_calendar that's `calendar.calendar_owner_id` + `calendar.practice_id` — NOT the acting user's `customer_id`/`clinic_id` from the JWT.

**Why:** an admin/clinicadmin frequently acts on behalf of another provider (create/update a Zoom meeting, edit someone's calendar). If you resolve from the JWT actor, you get the wrong person's value. Caught in VP-17190 PR review: `zoom.service` resolved `resolveProviderTimezone(customerId, practiceId)` from the JWT instead of `calendar.calendar_owner_id`/`practice_id`, so meetings booked for another provider used the actor's timezone.

**How to apply:** before passing ids into any per-owner lookup, ask "whose resource is this?" — if the method receives the resource object (the calendar/event), use ITS owner ids. Only use JWT actor ids when the data is genuinely about the caller themselves (e.g. "my own settings page"). Related: [[feedback_audit_callers_when_adding_fallback]].
