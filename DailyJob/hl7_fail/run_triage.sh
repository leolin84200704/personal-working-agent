#!/bin/bash
# hl7_file_input Daily Triage — runs via launchd at 4:00 AM daily
# Uses Claude Code CLI to execute the triage prompt

PROMPT_FILE="/Users/hung.l/src/vibrant-america-working-agent/DailyJob/hl7_fail/triage_prompt.md"
LOG_DIR="/Users/hung.l/src/vibrant-america-working-agent/DailyJob/hl7_fail"
LOG_FILE="${LOG_DIR}/run_$(date +%Y-%m-%d).log"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Headless runs must not touch Claude Code's native auto memory — the agent repo
# (STM/LTM/journal) is the system of record; a shadow store diverges silently.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

# Wait up to 60s for network
for i in $(seq 1 30); do
    if curl -sS --max-time 3 -o /dev/null https://api.anthropic.com/; then
        echo "[$(date)] Network ready (attempt $i)" >> "$LOG_FILE"
        break
    fi
    sleep 2
done

# --- VPN / prod-DB pre-flight -------------------------------------------
# Overnight the Cisco Secure Client VPN auto-disconnects and prod MySQL
# (3306) became unreachable at 4 AM on 2026-07-05/06 (while 443 worked).
# Internal endpoints (192.168.60.x gRPC) always require the VPN; the Azure
# MySQL host is reachable without it from some networks but not others.
# So: check actual DB reachability first, try one safe reconnect, and if
# still down write a BLOCKED report + notify, instead of burning claude
# attempts and risking a false "no failures".
DB_HOST="lisportalprod2.mysql.database.azure.com"
VPN_CLI="/opt/cisco/secureclient/bin/vpn"
VPN_SERVER="45.24.217.146"   # last known head-end (vpn stats > Server Address)
TRIAGE_REPORT="${LOG_DIR}/triage_$(date +%Y-%m-%d).md"

db_reachable() {
    nc -z -w 5 "$DB_HOST" 3306 >/dev/null 2>&1
}

if ! db_reachable; then
    echo "[$(date)] Pre-flight: ${DB_HOST}:3306 unreachable — VPN likely down, attempting reconnect" >> "$LOG_FILE"
    if [[ -x "$VPN_CLI" ]]; then
        # The CLI prints a transient ">> state: Unknown" first — only the LAST
        # state line is real. CAUTION: `vpn connect` tears down an existing
        # session before reconnecting (verified 2026-07-06), so only attempt
        # it when the state is unambiguously Disconnected.
        VPN_STATE=$("$VPN_CLI" state 2>/dev/null | grep '>> state:' | tail -1 | awk '{print $NF}')
        echo "[$(date)] Cisco Secure Client state: ${VPN_STATE:-unknown}" >> "$LOG_FILE"
        if [[ "$VPN_STATE" == "Disconnected" ]]; then
            # Best-effort headless reconnect. With SSO + the GUI agent holding
            # the connect capability this usually fails fast ("Connect
            # capability is unavailable"); /dev/null stdin avoids hanging.
            "$VPN_CLI" -s connect "$VPN_SERVER" < /dev/null >> "$LOG_FILE" 2>&1
        fi
    fi
    # Give the tunnel up to 60s to come up, then re-test
    for i in $(seq 1 12); do
        db_reachable && break
        sleep 5
    done
fi

if ! db_reachable; then
    echo "[$(date)] Pre-flight FAILED: 3306 still unreachable after reconnect attempt — skipping triage run" >> "$LOG_FILE"
    cat > "$TRIAGE_REPORT" <<EOF
# HL7 File Input Daily Triage — $(date +%Y-%m-%d)

## BLOCKED — VPN down, prod DB unreachable

- Pre-flight: \`${DB_HOST}:3306\` unreachable from this machine at $(date).
- Likely cause: Cisco Secure Client VPN not connected (it auto-disconnects overnight) and the current network path cannot reach the DB without it.
- A headless reconnect to \`${VPN_SERVER}\` was attempted and did not restore connectivity (SSO login is interactive; the GUI agent holds the connect capability).
- **No DB queries were run. This is NOT a "no failed records" result** — re-run manually after reconnecting the VPN.
EOF
    osascript -e 'display notification "VPN down — HL7 triage skipped (reconnect failed, needs interactive login)" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi
echo "[$(date)] Pre-flight OK: ${DB_HOST}:3306 reachable" >> "$LOG_FILE"
# -------------------------------------------------------------------------

PROMPT=$(cat "$PROMPT_FILE")
ATTEMPT=1
MAX_ATTEMPTS=3
SUCCESS=0

while [[ $ATTEMPT -le $MAX_ATTEMPTS ]]; do
    echo "=== HL7 Triage attempt $ATTEMPT/$MAX_ATTEMPTS started at $(date) ===" >> "$LOG_FILE"
    TMP=$(mktemp)

    claude -p "$PROMPT" \
        --model sonnet \
        --allowedTools "Bash,Read,Write,Edit,Grep,Glob" \
        --max-turns 30 \
        > "$TMP" 2>&1

    cat "$TMP" >> "$LOG_FILE"
    echo "=== HL7 Triage attempt $ATTEMPT finished at $(date) ===" >> "$LOG_FILE"

    if ! grep -q "API Error" "$TMP"; then
        SUCCESS=1
        rm -f "$TMP"
        break
    fi
    rm -f "$TMP"

    if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; then
        echo "[$(date)] Attempt $ATTEMPT hit API error, retrying in 30s..." >> "$LOG_FILE"
        sleep 30
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

if [[ $SUCCESS -eq 0 ]]; then
    echo "[$(date)] FAILED after $MAX_ATTEMPTS attempts" >> "$LOG_FILE"
    osascript -e 'display notification "HL7 Triage failed after retries" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi
