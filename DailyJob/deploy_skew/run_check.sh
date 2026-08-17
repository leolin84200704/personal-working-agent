#!/bin/bash
# Daily deploy-skew check for lis-backend-emr-v2. Installed via com.lis.deploy-skew.plist.
#
# ONPREM_SSH_PASSWORD_FILE must point at a 0600 file OUTSIDE this repo (an ssh key for the
# bastion is better and makes the variable unnecessary). Nothing secret goes in here.
set -uo pipefail
cd /Users/hung.l/src/vibrant-america-working-agent || exit 1

export ONPREM_SSH_PASSWORD_FILE="${ONPREM_SSH_PASSWORD_FILE:-$HOME/.config/lis-agent/onprem-ssh-password}"
OUT=$(python3 DailyJob/deploy_skew/check_deploy_skew.py 2>&1)
RC=$?
echo "$OUT"

# Exit 1 means something is stale, stuck, or unverifiable — all three need a human. A silent
# green run is the failure mode this job exists to prevent, so say something either way.
if [ $RC -ne 0 ]; then
  osascript -e 'display notification "emr-v2 deploy skew detected — see DailyJob/deploy_skew/" with title "LIS deploy check"' 2>/dev/null
fi
exit $RC
