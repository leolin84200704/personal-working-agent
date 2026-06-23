#!/bin/zsh
# Vibrant America nightly digest — headless Claude Code summarizes today's code changes
# (Vibrant-America org, read-only via gh) + Jira VP activity into
# long-term-memory/daily-digest/<DATE>.md, then commit+push to lis-code-agent main.
#
# Runs in an ISOLATED git worktree (this directory), NEVER in Leo's working repo, so it
# can never disturb his active branch. Scheduled via launchd at local midnight.

set -u

# launchd runs with a minimal PATH; make sure brew tools (claude, gh, git) resolve.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/hung.l/.lis-daily-digest/main"
LOG_DIR="$REPO/logs/daily-digest"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
LOG="$LOG_DIR/$STAMP.log"

cd "$REPO" || { echo "cannot cd $REPO" >&2; exit 1; }

PROMPT="$(cat "$REPO/scripts/daily-digest-prompt.md")"

{
  echo "=== Vibrant America daily digest run: $STAMP ==="
  echo "PATH=$PATH"
  echo "claude=$(command -v claude)  gh=$(command -v gh)"
  echo "--- gh auth ---"
  gh auth status 2>&1 | head -4
  echo "--- starting claude headless ---"
  claude -p "$PROMPT" \
    --dangerously-skip-permissions \
    2>&1
  echo "--- claude exit code: $? ---"
  echo "=== done: $(date +%Y-%m-%d_%H%M%S) ==="
} >>"$LOG" 2>&1
