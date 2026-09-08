#!/usr/bin/env bash
# VP-17766 end-to-end: book a Clinical Consult with contact_email + cc_emails, verify the
# stored recipients and the emitted email rows, then cancel the consult.
#
# Required env:
#   TOKEN                 provider JWT for the portal (localStorage jwtToken)
#   ENDPOINT              https://api.vibrant-america.com/v2/portal/trans-service(-st)/graphql
#   CALENDAR_URL          postgresql://...ehr-admin (no ?schema); SCHEMA=calendar_prod|calendar_dev_new
#   CLINICIAN_CALENDAR_ID / CLINICIAN_CUSTOMER_ID   the 150105 clinicadmin calendar + its owner id
#   PROVIDER_ID           the booking provider's customer_id (the JWT owner)
#   CONTACT_EMAIL         To override (e.g. your own mailbox)
#   CC_EMAILS             comma-separated CC list
# Optional: DAYS_AHEAD (default 5), STEP (availability|create|verify|cancel|all; default all), EVENT_ID (for verify/cancel)
set -euo pipefail
: "${TOKEN:?}" "${ENDPOINT:?}" "${CALENDAR_URL:?}" "${SCHEMA:?}" "${CLINICIAN_CALENDAR_ID:?}" "${CLINICIAN_CUSTOMER_ID:?}" "${PROVIDER_ID:?}" "${CONTACT_EMAIL:?}" "${CC_EMAILS:?}"
DAYS_AHEAD="${DAYS_AHEAD:-5}"; STEP="${STEP:-all}"
PSQL=/opt/homebrew/opt/libpq/bin/psql
gql() { curl -s -X POST "$ENDPOINT" -H "content-type: application/json" -H "Authorization: Bearer $TOKEN" -d "$1"; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); $1"; }

if [[ "$STEP" == "availability" || "$STEP" == "all" ]]; then
  START=$(date -u -v+${DAYS_AHEAD}d +%F); END=$(date -u -v+$((DAYS_AHEAD+7))d +%F)
  Q=$(python3 - "$CLINICIAN_CALENDAR_ID" "$CLINICIAN_CUSTOMER_ID" "$PROVIDER_ID" "$START" "$END" <<'PY'
import sys,json
cal,cust,prov,s,e=sys.argv[1:]
q='query($input: GetClinicianAvailabilityInput!){ getLabClinicianAvailability(input:$input){ provider_calendar_id provider_name timezone available_slots{ start_time end_time } } }'
print(json.dumps({"query":q,"variables":{"input":{"clinician_calendar_id":int(cal),"clinician_customer_id":int(cust),"provider_id":int(prov),"start_date":s,"end_date":e,"duration_minutes":30}}}))
PY
)
  gql "$Q" | json "
if d.get('errors'): print('ERRORS', d['errors']); sys.exit(1)
a=d['data']['getLabClinicianAvailability']; slots=a['available_slots']
print('provider_calendar_id', a['provider_calendar_id'], a['provider_name'], a['timezone'], 'slots', len(slots))
for s in slots[:5]: print('  ', s['start_time'], s['end_time'])
open('/tmp/vp17766_slot.json','w').write(json.dumps(slots[0]))"
fi

if [[ "$STEP" == "create" || "$STEP" == "all" ]]; then
  SLOT_START=$(python3 -c "import json;print(json.load(open('/tmp/vp17766_slot.json'))['start_time'])")
  SLOT_END=$(python3 -c "import json;print(json.load(open('/tmp/vp17766_slot.json'))['end_time'])")
  M=$(python3 - "$PROVIDER_ID" "$CLINICIAN_CALENDAR_ID" "$SLOT_START" "$SLOT_END" "$CONTACT_EMAIL" "$CC_EMAILS" <<'PY'
import sys,json
prov,cal,s,e,contact,cc=sys.argv[1:]
q='mutation($input: CreateEventByPatientInput!){ createEventByPatient(input:$input){ event_id event_title start_time end_time notes } }'
inp={"event_title":"VP-17766 E2E test consult (agent, will be cancelled)","customer_id":int(prov),"clinician_calendar_id":int(cal),
     "start_time":s,"end_time":e,"notes":f"[Name: VP-17766 E2E] [Email: {contact}] [Meeting Type: Call] VP-17766 automated end-to-end test - please ignore",
     "external_url":"000-000-0000","contact_email":contact,"cc_emails":cc.split(",")}
print(json.dumps({"query":q,"variables":{"input":inp}}))
PY
)
  gql "$M" | json "
if d.get('errors'): print('ERRORS', d['errors']); sys.exit(1)
ev=d['data']['createEventByPatient']; print('CREATED event_id', ev['event_id'], ev['start_time'])
open('/tmp/vp17766_event_id','w').write(str(ev['event_id']))"
fi

if [[ "$STEP" == "verify" || "$STEP" == "all" ]]; then
  EVENT_ID="${EVENT_ID:-$(cat /tmp/vp17766_event_id)}"
  $PSQL "$CALENDAR_URL" -X -q -At <<SQL
SET search_path=$SCHEMA;
\\echo --- v2_event recipients
SELECT event_id||'|'||coalesce(contact_email,'<null>')||'|'||array_to_string(cc_emails,',')||'|'||is_canceled||'|'||practice_id FROM v2_event WHERE event_id=$EVENT_ID;
\\echo --- participants (role|calendar|email)
SELECT ep.role||'|'||c.calendar_id||'|'||coalesce(c.calendar_owner_email,'')||'|'||array_to_string(c.notification_cc_emails,',') FROM v2_event_participant ep JOIN v2_calendar c ON c.calendar_id=ep.participant_calendar_id WHERE ep.event_id=$EVENT_ID;
SQL
fi

if [[ "$STEP" == "cancel" || "$STEP" == "all" ]]; then
  EVENT_ID="${EVENT_ID:-$(cat /tmp/vp17766_event_id)}"
  D=$(python3 -c "import json,sys;print(json.dumps({'query':'mutation(\$input: DeleteEventInput!){ deleteEventByPatient(input:\$input){ event_id success message } }','variables':{'input':{'event_id':int(sys.argv[1]),'is_canceled':True}}}))" "$EVENT_ID")
  gql "$D" | json "print('CANCEL', d.get('data') or d.get('errors'))"
  $PSQL "$CALENDAR_URL" -X -q -At -c "SET search_path=$SCHEMA; SELECT 'is_canceled='||is_canceled FROM v2_event WHERE event_id=$EVENT_ID"
fi
