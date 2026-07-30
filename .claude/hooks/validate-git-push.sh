#!/bin/bash
# Validate git push commands — block force push and push to protected branches.
# Called by Claude Code PreToolUse hook. Receives JSON on stdin.

COMMAND=$(cat | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Block force push. The force flag must be scoped to the push command itself:
# the old pattern was a bare `-f ` anywhere in the command, which blocked ordinary
# calls like `rm -f tmp.js`, `tail -f log`, `grep -f patterns` with a "force push"
# message (hit twice during the 2026-07-29 dream run). `[^;&|]*` keeps the match
# inside the same command segment, so `rm -f x && git push` is not force-push.
if echo "$COMMAND" | grep -qE 'push[^;&|]*(--force|[[:space:]]-f([[:space:]]|$))'; then
  echo "BLOCKED: force push 不允許。" >&2
  exit 2
fi

# Block push to protected branches.
# NOTE: this is the personal vibrant-america-working-agent repo — pushing to `main` is allowed
# here (the daily-digest job and manual knowledge consolidation land on main).
# master/staging stay protected; force-push is blocked above.
if echo "$COMMAND" | grep -qE 'push\s+\S+\s+(master|staging)(\s|$)'; then
  echo "BLOCKED: 不能直接 push 到 master/staging。" >&2
  exit 2
fi

exit 0
