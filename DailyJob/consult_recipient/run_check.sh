#!/bin/bash
# Daily consult-recipient check (VP-17825). Installed via com.lis.consult-recipient.plist.
#
# Reads calendar_prod through the LIS-transformer-v2 checkout's .env — nothing secret
# lives in this repo. Read-only: SELECTs only, no writes.
set -uo pipefail
cd /Users/hung.l/src/vibrant-america-working-agent || exit 1

export TRANSV2_DIR="${TRANSV2_DIR:-$HOME/src/LIS-transformer-v2}"
OUT=$(node DailyJob/consult_recipient/check_consult_recipients.js 2>&1)
RC=$?
echo "$OUT"

# Exit 1 means either a consult will get no reminder, or the check could not run.
# Both need a human — a silent green is exactly the failure this job guards against.
if [ $RC -ne 0 ]; then
  osascript -e 'display notification "Upcoming consult with no reminder recipient — see DailyJob/consult_recipient/" with title "LIS consult check"' 2>/dev/null
fi
exit $RC
