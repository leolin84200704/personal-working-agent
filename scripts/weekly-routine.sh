#!/bin/bash
# Weekly self-improvement routine. Idempotent. Designed for Sunday launchd.
# Sequence:
#   1. Refresh derived LTM files (failure index, rules constitution)
#   2. Sweep STM frontmatter for missing urgency tags
#   3. Recompute scores + rebuild indexes
#   4. Capture eval snapshot
#   5. Capture retrieval test snapshot
#   6. Compare with the previous week's snapshot, write logs/weekly-YYYY-MM-DD.md
#
# Each sub-step is wrapped so one failure doesn't abort the rest.
# Run manually with: bash scripts/weekly-routine.sh
set -uo pipefail

AGENT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$AGENT_ROOT"

DATE=$(date +%Y-%m-%d)
LOG_DIR="$AGENT_ROOT/logs"
mkdir -p "$LOG_DIR"
REPORT="$LOG_DIR/weekly-$DATE.md"
STDLOG="$LOG_DIR/launchd-weekly-stdout-$DATE.log"

# Dry-run prints the plan and exits before invoking python.
if [[ "${1:-}" == "--dry" ]]; then
    cat <<EOF
DRY RUN: would run weekly self-improvement
  Agent root: $AGENT_ROOT
  Date: $DATE
  Steps:
    1. python3 scripts/extract-failures.py
    2. python3 scripts/extract-rules.py
    3. python3 scripts/sweep-urgency.py
    4. python3 -c '... rebuild indexes'
    5. python3 scripts/eval.py --label weekly-$DATE
    6. python3 scripts/test-retrieval.py --label weekly-$DATE
    7. write $REPORT (diff with previous weekly snapshot)
EOF
    exit 0
fi

step() {
    local name=$1; shift
    echo "[$(date)] === $name ===" | tee -a "$STDLOG"
    if "$@" 2>&1 | tee -a "$STDLOG"; then
        echo "[$(date)] $name: ok" | tee -a "$STDLOG"
    else
        echo "[$(date)] $name: FAILED (non-fatal)" | tee -a "$STDLOG"
    fi
}

step "extract-failures"  python3 scripts/extract-failures.py
step "extract-rules"     python3 scripts/extract-rules.py
step "sweep-urgency"     python3 scripts/sweep-urgency.py
step "rebuild-scores"    python3 -c "
from src.memory.scorer import MemoryScorer
s = MemoryScorer()
for tier in ('stm','ltm','archive'):
    s.update_scores_in_files(tier)
s.rebuild_all_indexes()
print('indexes rebuilt')
"
step "eval-snapshot"     python3 scripts/eval.py --label "weekly-$DATE"
step "retrieval-test"    python3 scripts/test-retrieval.py --label "weekly-$DATE"

# Build the human-readable report: diff against the previous weekly eval
# snapshot. Exclude *retrieval* files (they have their own diff below) and
# today's own snapshot so we land on a true prior-week file.
prev=$(ls -1 eval-output/*-weekly-*.json 2>/dev/null \
        | grep -v retrieval \
        | grep -v "eval-output/${DATE}-weekly-" \
        | sort | tail -1)
prev_label=""
if [[ -n "$prev" ]]; then
    prev_label=$(basename "$prev" .json | sed 's/.*-weekly-//')
fi

{
    echo "# Weekly Self-Improvement Report — $DATE"
    echo
    if [[ -n "$prev_label" ]]; then
        echo "Comparing against previous weekly snapshot: $prev_label"
        echo
        echo "## Eval diff"
        echo '```'
        python3 scripts/eval.py --diff "weekly-$prev_label" 2>&1 | sed -n '/## Diff/,$p'
        echo '```'
        echo
        echo "## Retrieval diff"
        echo '```'
        python3 scripts/test-retrieval.py --diff "weekly-$prev_label" 2>&1 | sed -n '/## Diff/,$p'
        echo '```'
    else
        echo "_No previous weekly snapshot found — this is the first weekly run._"
        echo
        echo "## Current eval"
        echo '```'
        python3 scripts/eval.py 2>&1 | tail -25
        echo '```'
        echo
        echo "## Current retrieval"
        echo '```'
        python3 scripts/test-retrieval.py 2>&1 | tail -10
        echo '```'
    fi
    echo
    echo "## Notes (manual addendum)"
    echo "- (leave space for Leo's observations next week)"
} > "$REPORT"

echo "[$(date)] Weekly routine done. Report: $REPORT" | tee -a "$STDLOG"
