#!/bin/bash
set -uo pipefail

AGENT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$AGENT_ROOT"

# The dream must never read/write Claude Code's native auto memory: this repo
# (STM/LTM/journal) is the single system of record, and headless runs writing to
# ~/.claude/projects/*/memory/ create a diverging shadow store. The interactive
# side is turned off via autoMemoryEnabled in .claude/settings.json; this covers
# the headless side, which that setting does not reach.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

# Pin the model explicitly: headless `claude -p` without --model inherits the
# user's interactive default from ~/.claude/settings.json — if that default is a
# premium model, every nightly dream silently bills it (same failure class as
# the jac/gpa incidents fixed 2026-08-15).
DREAM_MODEL="${DREAM_MODEL:-fable}"

DATE=$(date +%Y-%m-%d)
LOG_DIR="$AGENT_ROOT/logs"
mkdir -p "$LOG_DIR"

# The dated log is claimed BEFORE the guards below, not after them. Until 2026-08-24
# the dirty-memory abort ran while LOG_FILE was still unset, so its
# `tee -a "${LOG_FILE:-/dev/null}"` discarded the message and the only surviving copy
# went to the launchd stdout file, which never rotates. Three consecutive aborts
# (08-21..08-23) were invisible for that reason: no dated log was created, so the
# newest logs/launchd-stdout-*.log still read 08-20 and nothing else contradicted it.
LOG_FILE="$LOG_DIR/launchd-stdout-$DATE.log"

# Cross-job state. Home-relative on purpose: the daily-digest job runs in its own
# worktree and must be able to read this without knowing where this repo is checked
# out, and without reaching into Leo's working copy. Deliberately NOT inside the
# repo — a status stamp is not memory and must never ride along in a dream commit.
STATE_DIR="${DREAM_STATE_DIR:-$HOME/.lis-agent-state/dream}"
mkdir -p "$STATE_DIR"
STATUS_FILE="$STATE_DIR/status"
LAST_SUCCESS_FILE="$STATE_DIR/last-success"

# When did a run last actually finish? Two things derive from this single answer:
# the Phase 0.5 closeout-audit window (so an aborted night's closures still get
# audited the next time a run succeeds) and the digest's staleness report.
LAST_SUCCESS=$(cat "$LAST_SUCCESS_FILE" 2>/dev/null || true)
read -r CLOSEOUT_SINCE NIGHTS_SINCE_SUCCESS <<<"$(python3 - "${LAST_SUCCESS:-}" <<'PY'
import sys
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
raw = (sys.argv[1] if len(sys.argv) > 1 else '').strip()
try:
    last = datetime.fromisoformat(raw.replace('Z', '+00:00'))
except ValueError:
    # Nothing on record (first run after this change, or state dir wiped) — keep the
    # original 24h window rather than inventing an unbounded one.
    print((now - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ'), 0)
else:
    print(last.strftime('%Y-%m-%dT%H:%M:%SZ'),
          max(0, round((now - last).total_seconds() / 86400)))
PY
)"

# Every terminal path records why it ended. A night that produced no distillation
# should be a fact someone can read the next morning, not an absence nobody notices.
# The lock-held SKIP path deliberately does not write here: that instance has no
# outcome of its own, and overwriting would hide the running instance's result.
record_outcome() {
    local outcome="$1"
    local detail now
    detail=$(printf '%s' "${2:-}" | tr '\n' ';' | tr -s ' ')
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    {
        echo "date=$DATE"
        echo "finished_at=$now"
        echo "outcome=$outcome"
        if [[ "$outcome" == "success" ]]; then
            # This run IS the latest success — report it as such, not the previous one.
            echo "nights_since_success=0"
            echo "last_success=$now"
        else
            echo "nights_since_success=$NIGHTS_SINCE_SUCCESS"
            echo "last_success=${LAST_SUCCESS:-never}"
        fi
        echo "detail=$detail"
        echo "log=$LOG_FILE"
    } > "$STATUS_FILE"
    if [[ "$outcome" == "success" ]]; then
        printf '%s\n' "$now" > "$LAST_SUCCESS_FILE"
    fi
}

# A dirty memory file is a signal, not an obstacle. On 2026-08-19 an uncommitted
# regeneration of long-term-memory/failures.md — 49 links short and missing an
# entry that existed nowhere else — sat in the working tree. The dream agent
# pulled with `--rebase --autostash`, distilled from the committed file, committed
# its own result, and the autostash pop then restored the broken version on top of
# it. The loss was invisible for a day and would have landed on the next add -A.
#
# So: refuse to start while tracked memory files carry uncommitted edits. Whoever
# wrote them either meant to commit them or did not; both need a human, and a
# night without distillation costs less than a night of silent overwriting.
# Untracked files are fine — a new STM is exactly what a dream run is for.
DIRTY_MEMORY=$(git -C "$AGENT_ROOT" status --porcelain -- \
    long-term-memory storage/short_term_memory journal 2>/dev/null | grep -v '^??' || true)
if [[ -n "$DIRTY_MEMORY" && "${DREAM_ALLOW_DIRTY_MEMORY:-0}" != "1" ]]; then
    {
        echo "[$(date)] ABORT: uncommitted changes to tracked memory files"
        echo "$DIRTY_MEMORY"
        echo "Inspect them (git diff), then commit or discard, and re-run."
        echo "To run anyway: DREAM_ALLOW_DIRTY_MEMORY=1 $0"
        if [[ -n "$LAST_SUCCESS" ]]; then
            echo "Nights since the last successful run ($LAST_SUCCESS): $NIGHTS_SINCE_SUCCESS."
        else
            echo "No successful run on record."
        fi
    } | tee -a "$LOG_FILE"
    record_outcome abort_dirty_memory "$DIRTY_MEMORY"
    osascript -e 'display notification "Dream aborted — uncommitted memory changes need a decision" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi

if [[ "${1:-}" == "--dry" ]]; then
    echo "DRY RUN: would execute dream pipeline"
    echo "  Agent root: $AGENT_ROOT"
    echo "  Date: $DATE"
    echo "  Log file: $LOG_FILE"
    echo "  State dir: $STATE_DIR"
    echo "  Last success: ${LAST_SUCCESS:-never} (nights since: $NIGHTS_SINCE_SUCCESS)"
    echo "  Closeout window since: $CLOSEOUT_SINCE"
    echo "  Command: claude -p \"\$(cat scripts/dream.md)\" --model $DREAM_MODEL --allowedTools Read,Write,Edit,Glob,Grep,Bash"
    exit 0
fi

# Single-instance guard. Two dream runs must never overlap: on 2026-07-29 three
# instances were live at once (a 17:03 run still inside its retry loop, the 18:30
# launchd run, and a manually invoked one). The winning run consolidated and
# committed at 19:39:03; the losing run then reached its own post-dream
# extract-failures.py at 19:39:43 and overwrote long-term-memory/failures.md with
# a score=0.0 stub (129 lines of links dropped). Concurrent consolidation can also
# double-write LTM sections and race the _index.md rebuilds.
# mkdir is the atomic primitive here — macOS bash has no flock.
LOCK_DIR="$AGENT_ROOT/.dream.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if [[ -n "${LOCK_PID:-}" ]] && kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$(date)] SKIP: dream already running (pid $LOCK_PID) — this instance exits" | tee -a "$LOG_FILE"
        exit 0
    fi
    echo "[$(date)] Stale lock (pid ${LOCK_PID:-unknown} gone) — taking it over" | tee -a "$LOG_FILE"
    rm -rf "$LOCK_DIR"
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "[$(date)] FATAL: cannot acquire $LOCK_DIR" | tee -a "$LOG_FILE"
        exit 1
    fi
fi
echo $$ > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

echo "[$(date)] Starting dream pipeline..." | tee -a "$LOG_FILE"
echo "  Agent root: $AGENT_ROOT" | tee -a "$LOG_FILE"

# A missing claude binary must fail loudly — previously it produced no dream
# log and no notification (output had no "API Error" so it looked like success).
if ! command -v claude >/dev/null 2>&1; then
    echo "[$(date)] FATAL: claude CLI not found on PATH ($PATH)" | tee -a "$LOG_FILE"
    record_outcome failed_no_cli "claude not on PATH: $PATH"
    osascript -e 'display notification "claude CLI not found — dream pipeline cannot run" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi

# Wait up to 60s for network (just woken from sleep may need a moment)
for i in $(seq 1 30); do
    if curl -sS --max-time 3 -o /dev/null https://api.anthropic.com/; then
        echo "[$(date)] Network ready (attempt $i)" | tee -a "$LOG_FILE"
        break
    fi
    sleep 2
done

# The run context is appended by the runner rather than hardcoded in dream.md so the
# closeout window is computed, not assumed. Phase 0.5 used a fixed "last 24h": after
# the 08-21..08-23 aborts, VP-17584 (closed 08-21) fell outside every subsequent
# window and would never have been audited by any run.
PROMPT="$(cat scripts/dream.md)

---

## Run context (generated by run-dream.sh)

These values are computed from the recorded state of previous runs and OVERRIDE any
default window named in the phases above.

- \`CLOSEOUT_SINCE\`: $CLOSEOUT_SINCE
- \`LAST_SUCCESSFUL_RUN\`: ${LAST_SUCCESS:-never}
- \`NIGHTS_SINCE_SUCCESS\`: $NIGHTS_SINCE_SUCCESS
"
ATTEMPT=1
MAX_ATTEMPTS=3
SUCCESS=0

while [[ $ATTEMPT -le $MAX_ATTEMPTS ]]; do
    echo "[$(date)] === Dream attempt $ATTEMPT/$MAX_ATTEMPTS ===" | tee -a "$LOG_FILE"
    TMP=$(mktemp)
    claude -p "$PROMPT" \
        --model "$DREAM_MODEL" \
        --allowedTools "Read,Write,Edit,Glob,Grep,Bash" \
        > "$TMP" 2>&1
    CLAUDE_EXIT=$?
    cat "$TMP" | tee -a "$LOG_FILE"

    # Success requires BOTH zero exit and no API error — grepping alone let
    # hard failures (crash, command error) pass as success.
    if [[ $CLAUDE_EXIT -eq 0 ]] && ! grep -q "API Error" "$TMP"; then
        SUCCESS=1
        rm -f "$TMP"
        break
    fi
    rm -f "$TMP"

    if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; then
        echo "[$(date)] Attempt $ATTEMPT hit API error, retrying in 30s..." | tee -a "$LOG_FILE"
        sleep 30
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

if [[ $SUCCESS -eq 0 ]]; then
    echo "[$(date)] FAILED after $MAX_ATTEMPTS attempts" | tee -a "$LOG_FILE"
    record_outcome failed_api "claude exited non-zero or reported API Error on $MAX_ATTEMPTS attempts"
    osascript -e 'display notification "Dream pipeline failed after retries" with title "LIS Code Agent" sound name "Basso"' >/dev/null 2>&1 || true
    exit 1
fi

# Post-dream: refresh failure index + snapshot evaluation metrics.
# Both are idempotent. Failures here are logged but do not fail the pipeline.
echo "[$(date)] Post-dream: refresh failure index" | tee -a "$LOG_FILE"
if ! python3 scripts/extract-failures.py 2>&1 | tee -a "$LOG_FILE"; then
    echo "[$(date)] WARN: extract-failures.py failed (non-fatal)" | tee -a "$LOG_FILE"
fi

# Commit the index this run just regenerated. Without this the run finishes with
# long-term-memory/failures.md dirty, and the dirty-memory guard above then
# aborts the NEXT night — the run locks its successor out of the room.
#
# It is intermittent, which is why it kept coming back: extract-failures.py is
# idempotent, so a night that distilled nothing new leaves no diff and nothing
# blocks. A night that DID distil something leaves a diff, and the more
# productive the run, the more certain it is to block the next one. Observed
# 2026-08-19, 2026-08-21..23 and 2026-08-25.
#
# Scoped to exactly this one path: the guard exists because a human must decide
# about memory files somebody else left dirty, and that stays true. This commits
# only the artifact this run produced itself, and only when it actually changed.
if ! git -C "$AGENT_ROOT" diff --quiet -- long-term-memory/failures.md 2>/dev/null; then
    if git -C "$AGENT_ROOT" add long-term-memory/failures.md &&
       git -C "$AGENT_ROOT" commit -q -m "[dream] refresh failure index ($DATE)" \
           -- long-term-memory/failures.md; then
        echo "[$(date)] Committed regenerated failure index" | tee -a "$LOG_FILE"
    else
        echo "[$(date)] WARN: could not commit failure index — the next run will abort on it" \
            | tee -a "$LOG_FILE"
    fi
fi

echo "[$(date)] Post-dream: capture eval snapshot dream-$DATE" | tee -a "$LOG_FILE"
if ! python3 scripts/eval.py --label "dream-$DATE" 2>&1 | tail -30 | tee -a "$LOG_FILE"; then
    echo "[$(date)] WARN: eval.py failed (non-fatal)" | tee -a "$LOG_FILE"
fi

# Recorded last, after the post-dream steps: "success" means the whole pipeline ran,
# and it is this stamp that moves the next run's closeout window forward.
record_outcome success "closeout window covered: $CLOSEOUT_SINCE onwards"

echo "[$(date)] Dream pipeline complete. Log: $LOG_FILE" | tee -a "$LOG_FILE"
