#!/bin/bash
# PreToolUse guard for verification assets (eval tasks, hooks, graders).
#
# Rationale (ENFORCEMENT-LADDER.md): these files are the agent's reward
# signal — the things that judge the agent's own work. An agent editing an
# existing expect-regex, hook, or grader can turn a fail into a pass with no
# one noticing (same-author code+test has weak evidential value).
#
# Policy: ADDING a new asset is free (additions are cheap to review).
# MODIFYING an existing asset pauses once per session+file (exit 2) and
# requires stating explicit human approval, then the retry passes.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
SESSION=$(echo "$INPUT" | jq -r '.session_id // "nosession"')
[ -z "$FILE" ] && exit 0

PROTECTED_RE='(/eval-tasks/[^/]+\.md$|/hooks/[^/]+\.sh$|/run-regression\.py$)'
echo "$FILE" | grep -qE "$PROTECTED_RE" || exit 0

# New file → allowed. What needs protection is mutation of existing assertions.
[ ! -e "$FILE" ] && exit 0

KEY=$(printf '%s' "$FILE" | shasum | cut -c1-12)
MARKER="${TMPDIR:-/tmp}/verif-asset-ok-${SESSION}-${KEY}"
[ -f "$MARKER" ] && exit 0
touch "$MARKER"

cat >&2 <<EOF
PAUSED (once per file per session): $FILE is a verification asset — part of
the reward signal that judges the agent's own work (eval task / hook / grader).
Modifying existing assertions weakens the evidence unless a human approved it.
If Leo explicitly approved this exact change, state so and re-run — it will
pass. Otherwise stop and propose the change instead of applying it.
After any eval-task/grader edit, re-validate the grader:
  python3 scripts/run-regression.py --check {task-id} --answer "{known-good}"
EOF
exit 2
