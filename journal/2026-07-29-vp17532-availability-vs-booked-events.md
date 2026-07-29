# 2026-07-29 — VP-17532: "booked outside my availability" = config edited after bookings

Related: VP-17532, VP-16850, VP-17190, VP-16499, VP-16410

## What happened
P1 bug: Clinical Educator Dana Filatova (150105, calendar 30794) reported consults booked at ~3:30pm Mon/Wed outside her availability slots. Found 6 offending "Provider Consult" events created 7/15–7/21 by 6 different providers via the normal portal flow.

## Reasoning trail (what was explored and excluded)
1. Screenshot slots matched current v2_schedule exactly → the UI wasn't lying about current config.
2. Suspected VP-16499 pooled multi-clinician slots leaking the wrong clinician: 3 of the offending times exactly matched Suzette Garcia's current windows — seductive, but reschedule cancel-and-rebook leaves cancelled twins and there were none; createEvent (no validation) ruled out by participant signature (clinicadmin/no_response + patient/accepted = createEventByPatient legacy path).
3. Suspected timezone: resolved Dana's provider tz setting live via core SettingService gRPC (grpcurl + client-credentials token from transformer .env) = America/New_York since 6/24. No tz interpretation of her CURRENT schedule makes the booked times pass validateSlotAvailability, which has been in prod since 4/30.
4. Resolution: v2_schedule has no timestamps/history, but updateWorkingHours = deleteMany + createMany → her row ids (1606–1630) being the global table max proved her weekly hours were rewritten after ALL other calendars — i.e., after the last offending booking (7/21). Bookings were valid when made; nothing re-validates existing events when availability shrinks.
5. Defensive is_available=false exceptions she added from 7/27 corroborate the timeline. Accession-dup side-quest (2604246499 on two active events) = legit manual reset 7/14, not a bug.

## Outcome
Leo posted the English explanation and set the ticket to Inactive. Remaining ops item (future event 8/3 Mon 15:00 ET outside new hours) handed to clinical team. No code change.

## Lessons
- Before diagnosing an engine bug, check whether the config the data violates existed when the data was written. Config stores without history ≠ config never changed.
- Delete-and-recreate write patterns make surrogate-key ordering a usable change-dating tool.
- Product gap noted (not ticketed per Leo's call): shrinking weekly hours could surface future bookings now outside the new hours.

## User's words
- "把這段寫成英文我要回去comment" → posted (condensed by Leo himself), then "done".
