#!/bin/bash
# Block destructive git commands: reset --hard, checkout ., clean -fd
# Called by Claude Code PreToolUse hook. Receives JSON on stdin.

COMMAND=$(cat | jq -r '.tool_input.command // empty')
[ -z "$COMMAND" ] && exit 0

if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard'; then
  echo "BLOCKED: git reset --hard 不允許。" >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
  echo "BLOCKED: git clean -f 不允許。" >&2
  exit 2
fi

exit 0
