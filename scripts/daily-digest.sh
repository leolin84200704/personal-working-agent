#!/bin/zsh
# Vibrant America nightly digest — headless Claude Code summarizes today's code changes
# (Vibrant-America org, read-only via gh) + Jira VP activity into
# long-term-memory/daily-digest/<DATE>.md, then commit+push to lis-code-agent auto/daily-digest.
#
# Runs in an ISOLATED git worktree (this directory), NEVER in Leo's working repo.
# Scheduled via launchd at local midnight. The Mac may be asleep at fire time, so this
# script is hardened against the just-woken state: network may be down and the macOS
# keychain may be locked. Mitigations: wait for network, read gh token from a file
# (not the keychain), prevent idle-sleep mid-run (caffeinate), and retry once.

set -u

# launchd runs with a minimal PATH; make sure brew tools (claude, gh, git) resolve.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/hung.l/.lis-daily-digest/main"
JOB_HOME="/Users/hung.l/.lis-daily-digest"
LOG_DIR="$REPO/logs/daily-digest"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
LOG="$LOG_DIR/$STAMP.log"

cd "$REPO" || { echo "cannot cd $REPO" >&2; exit 1; }

# Decouple gh + git-push auth from the macOS keychain (locked while the Mac is asleep):
# use a token file if present. gh api AND the gh git-credential helper both honor GH_TOKEN.
if [ -r "$JOB_HOME/.gh_token" ]; then
  export GH_TOKEN="$(cat "$JOB_HOME/.gh_token")"
fi

PROMPT="$(cat "$REPO/scripts/daily-digest-prompt.md")"

{
  echo "=== Vibrant America daily digest run: $STAMP ==="
  echo "PATH=$PATH"
  echo "claude=$(command -v claude)  gh=$(command -v gh)"
  echo "GH_TOKEN set: $([ -n "${GH_TOKEN:-}" ] && echo yes || echo no)"

  # The Mac may have just woken — wait for network (Wi-Fi reconnect) before doing anything.
  net_ok=0
  for i in $(seq 1 30); do
    if curl -s -m 8 -o /dev/null https://api.anthropic.com/ ; then net_ok=1; break; fi
    echo "network not ready (attempt $i/30), waiting 10s..."
    sleep 10
  done
  echo "--- network ready: $net_ok ---"
  if [ "$net_ok" -ne 1 ]; then
    echo "ABORT: network never came up after 5 min."
    echo "=== done: $(date +%Y-%m-%d_%H%M%S) ==="
    exit 1
  fi

  echo "--- gh auth (via GH_TOKEN, no keychain) ---"
  gh auth status 2>&1 | head -4

  # Run claude, prevented from idle-sleeping mid-run (caffeinate -i), with one retry.
  rc=1
  for attempt in 1 2; do
    echo "--- claude attempt $attempt ---"
    caffeinate -i claude -p "$PROMPT" --dangerously-skip-permissions 2>&1
    rc=$?
    echo "--- claude exit code: $rc (attempt $attempt) ---"
    [ "$rc" -eq 0 ] && break
    echo "claude failed; retrying in 30s..."
    sleep 30
  done

  echo "=== done: $(date +%Y-%m-%d_%H%M%S) (final rc=$rc) ==="
} >>"$LOG" 2>&1
