#!/bin/bash
# Validate git push commands — block force push and push to protected branches.
# Called by Claude Code PreToolUse hook. Receives JSON on stdin.

COMMAND=$(cat | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

# Block force push
if echo "$COMMAND" | grep -qE '\-\-force|\-f '; then
  echo "BLOCKED: force push 不允許。" >&2
  exit 2
fi

# Block push to protected branches
if echo "$COMMAND" | grep -qE 'push\s+\S+\s+(main|master|staging)(\s|$)'; then
  echo "BLOCKED: 不能直接 push 到 main/master/staging。" >&2
  exit 2
fi

exit 0
