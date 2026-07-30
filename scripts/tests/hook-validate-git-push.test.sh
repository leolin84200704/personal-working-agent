#!/bin/bash
# Exercise .claude/hooks/validate-git-push.sh against representative commands.
HOOK=/Users/hung.l/src/vibrant-america-working-agent/.claude/hooks/validate-git-push.sh
run() {
  out=$(printf '{"tool_input":{"command":%s}}' "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" | "$HOOK" 2>&1)
  printf 'exit=%s | %-42s | %s\n' "$?" "$1" "$out"
}
echo "--- must be BLOCKED (exit 2) ---"
run 'git push --force origin main'
run 'git push -f origin main'
run 'git push origin main -f'
run 'git -C ~/src/x push -f'
run 'git push origin master'
run 'git push origin staging'
echo "--- must be ALLOWED (exit 0) ---"
run 'git push origin main'
run 'git push -u origin bugfix/leo/x'
run 'rm -f tmp.js'
run 'tail -f logs/app.log'
run 'grep -f pats file'
run 'ps -f'
run 'rm -f a.js && git push origin main'
