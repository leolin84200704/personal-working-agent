#!/bin/bash
# Result-delivery failure watch — runs via launchd (see com.lis.result-fail-watch.plist).
#
# Deterministic: no Claude CLI, just the runner. Report-only unless AUTO_REPUSH=1 is
# exported in the plist.

JOB_DIR="/Users/hung.l/src/vibrant-america-working-agent/DailyJob/result_fail"
LOG_FILE="${JOB_DIR}/run_$(date +%Y-%m-%d).log"
REPORT="${JOB_DIR}/report_$(date +%Y-%m-%d).md"
# System python is the one with pymysql installed (same as the hl7_fail runner).
PYTHON="/usr/bin/python3"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

DB_HOST="lisportalprod2.mysql.database.azure.com"

db_reachable() { nc -z -w 5 "$DB_HOST" 3306 >/dev/null 2>&1; }

# Same pre-flight discipline as hl7_fail: the overnight VPN drop makes 3306 unreachable,
# and an unreachable DB must be reported as BLOCKED. An empty result set would otherwise
# read as "no failures", which is the one conclusion this job must never reach by accident.
if ! db_reachable; then
    echo "[$(date)] 3306 unreachable — waiting up to 60s" >> "$LOG_FILE"
    for _ in $(seq 1 12); do
        db_reachable && break
        sleep 5
    done
fi

if ! db_reachable; then
    echo "[$(date)] BLOCKED: ${DB_HOST}:3306 unreachable — no queries run" >> "$LOG_FILE"
    cat > "$REPORT" <<EOF
# Result Delivery Failure Watch — $(date +%Y-%m-%d)

## BLOCKED — prod DB unreachable

\`${DB_HOST}:3306\` was unreachable at $(date) (VPN is the usual cause).

**No queries ran. This is NOT a "no failures" result.** Re-run after reconnecting:
\`${JOB_DIR}/run_result_fail.sh\`
EOF
    osascript -e 'display notification "Result failure watch BLOCKED — prod DB unreachable" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi

echo "=== result-fail watch started $(date) ===" >> "$LOG_FILE"
"$PYTHON" "${JOB_DIR}/result_fail_runner.py" >> "$LOG_FILE" 2>&1
STATUS=$?
echo "=== finished $(date) (exit ${STATUS}) ===" >> "$LOG_FILE"

if [[ $STATUS -ne 0 ]]; then
    osascript -e 'display notification "Result failure watch errored — see run log" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
fi

exit $STATUS
