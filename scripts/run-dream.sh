#!/bin/bash
set -euo pipefail

AGENT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$AGENT_ROOT"

DATE=$(date +%Y-%m-%d)
LOG_DIR="$AGENT_ROOT/logs"
mkdir -p "$LOG_DIR"

if [[ "${1:-}" == "--dry" ]]; then
    echo "DRY RUN: would execute dream pipeline"
    echo "  Agent root: $AGENT_ROOT"
    echo "  Date: $DATE"
    echo "  Command: claude -p \"\$(cat scripts/dream.md)\" --allowedTools Read,Write,Edit,Glob,Grep,Bash"
    exit 0
fi

echo "[$(date)] Starting dream pipeline..."
echo "  Agent root: $AGENT_ROOT"

claude -p "$(cat scripts/dream.md)" \
    --allowedTools "Read,Write,Edit,Glob,Grep,Bash" \
    2>&1 | tee "$LOG_DIR/launchd-stdout-$DATE.log"

echo "[$(date)] Dream pipeline complete. Log: $LOG_DIR/launchd-stdout-$DATE.log"
