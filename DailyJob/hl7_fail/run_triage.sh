#!/bin/bash
# hl7_file_input Daily Triage — runs via launchd at 4:00 AM daily
# Uses Claude Code CLI to execute the triage prompt

PROMPT_FILE="/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail/triage_prompt.md"
LOG_DIR="/Users/hung.l/src/lis-code-agent/DailyJob/hl7_fail"
LOG_FILE="${LOG_DIR}/run_$(date +%Y-%m-%d).log"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Wait up to 60s for network
for i in $(seq 1 30); do
    if curl -sS --max-time 3 -o /dev/null https://api.anthropic.com/; then
        echo "[$(date)] Network ready (attempt $i)" >> "$LOG_FILE"
        break
    fi
    sleep 2
done

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
