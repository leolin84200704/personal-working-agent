#!/bin/bash
# AI-native bug watch — scheduled triage of newly created bug tickets.
# Runs via launchd every 2 hours (com.lis.bug-watch.plist, odd hours at :30).
# Lookback is dynamic: covers everything since the newest previous watch
# report (+1h overlap for dedupe), clamped to [3, 24]h — so runs missed
# while the Mac sleeps are caught up in one sweep on wake.
# Install: cp DailyJob/bug_watch/com.lis.bug-watch.plist ~/Library/LaunchAgents/ \
#          && launchctl load ~/Library/LaunchAgents/com.lis.bug-watch.plist

AGENT_ROOT="/Users/hung.l/src/vibrant-america-working-agent"
WATCH_DIR="${AGENT_ROOT}/DailyJob/bug_watch"
PROMPT_FILE="${WATCH_DIR}/watch_prompt.md"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Headless runs must not touch Claude Code's native auto memory (the agent repo
# is the system of record), and must pin the model — an unpinned `claude -p`
# inherits the user's interactive default and silently bills it every 2 hours.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
BUGWATCH_MODEL="${BUGWATCH_MODEL:-sonnet}"

# Dynamic lookback: hours since the newest previous report, +1h overlap.
LAST_REPORT=$(ls -t "${WATCH_DIR}"/watch_*.md 2>/dev/null | head -1)
if [[ -n "$LAST_REPORT" ]]; then
    LAST_TS=$(stat -f %m "$LAST_REPORT")
    NOW_TS=$(date +%s)
    LOOKBACK_HOURS=$(( (NOW_TS - LAST_TS) / 3600 + 1 ))
else
    LOOKBACK_HOURS=17
fi
[[ $LOOKBACK_HOURS -lt 3 ]] && LOOKBACK_HOURS=3
[[ $LOOKBACK_HOURS -gt 24 ]] && LOOKBACK_HOURS=24

RUN_TAG=$(date +%H%M)
LOG_FILE="${WATCH_DIR}/run_$(date +%Y-%m-%d)_${RUN_TAG}.log"
REPORT_FILE="${WATCH_DIR}/watch_$(date +%Y-%m-%d)_${RUN_TAG}.md"

# Wait up to 60s for network
for i in $(seq 1 30); do
    if curl -sS --max-time 3 -o /dev/null https://api.anthropic.com/; then
        echo "[$(date)] Network ready (attempt $i)" >> "$LOG_FILE"
        break
    fi
    sleep 2
done

# VPN/DB pre-flight: if the VPN is down (prod DB unreachable), skip this run
# entirely — the next 2-hourly run's dynamic lookback covers the gap, since
# no report is written for skipped runs. No reconnect attempt here (SSO is
# interactive; `vpn connect` can tear down a live session), and no
# notification (overnight the VPN is routinely down — 12 pings would be noise).
DB_HOST="lisportalprod2.mysql.database.azure.com"
db_reachable() { nc -z -w 5 "$DB_HOST" 3306 >/dev/null 2>&1; }

if ! db_reachable; then
    echo "[$(date)] Pre-flight: ${DB_HOST}:3306 unreachable (VPN down) — skipping this run" >> "$LOG_FILE"
    exit 0
fi
echo "[$(date)] Run=${RUN_TAG} lookback=${LOOKBACK_HOURS}h DB=up" >> "$LOG_FILE"

PROMPT=$(sed -e "s/{{LOOKBACK_HOURS}}/${LOOKBACK_HOURS}/g" \
             -e "s|{{REPORT_FILE}}|${REPORT_FILE}|g" "$PROMPT_FILE")

ATTEMPT=1
MAX_ATTEMPTS=2
SUCCESS=0
while [[ $ATTEMPT -le $MAX_ATTEMPTS ]]; do
    echo "=== Bug watch attempt $ATTEMPT/$MAX_ATTEMPTS started at $(date) ===" >> "$LOG_FILE"
    TMP=$(mktemp)
    cd "$AGENT_ROOT" && claude -p "$PROMPT" \
        --model "$BUGWATCH_MODEL" \
        --allowedTools "Bash,Read,Write,Edit,Grep,Glob" \
        --max-turns 80 \
        > "$TMP" 2>&1
    cat "$TMP" >> "$LOG_FILE"
    echo "=== Bug watch attempt $ATTEMPT finished at $(date) ===" >> "$LOG_FILE"
    if ! grep -q "API Error" "$TMP"; then
        SUCCESS=1; rm "$TMP"; break
    fi
    rm "$TMP"
    [[ $ATTEMPT -lt $MAX_ATTEMPTS ]] && sleep 30
    ATTEMPT=$((ATTEMPT + 1))
done

if [[ $SUCCESS -eq 1 && -f "$REPORT_FILE" ]]; then
    # With 12 runs/day, only notify when there is actually something new.
    SUMMARY=$(grep -m1 '^- Total' "$REPORT_FILE" 2>/dev/null || echo "")
    NEW_COUNT=$(echo "$SUMMARY" | grep -o 'Total new: [0-9]*' | grep -o '[0-9]*$')
    if [[ -n "$NEW_COUNT" && "$NEW_COUNT" -gt 0 ]]; then
        osascript -e "display notification \"${SUMMARY}\" with title \"Bug Watch (${RUN_TAG})\"" >/dev/null 2>&1 || true
    fi
else
    osascript -e 'display notification "Bug watch run failed — check log" with title "Bug Watch" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi
