#!/bin/bash
# Exercise .claude/hooks/validate-git-push.sh against representative commands.
# The protected-branch policy is repo-aware, so each case carries a cwd:
#   PERSONAL = this working-agent repo (main allowed), WORK = a Vibrant work repo (main blocked).
HOOK=/Users/hung.l/src/vibrant-america-working-agent/.claude/hooks/validate-git-push.sh
PERSONAL=/Users/hung.l/src/vibrant-america-working-agent
WORK=/Users/hung.l/src/lis-backend-emr-v2

fails=0
# run <expected_exit> <command> <cwd>
run() {
  local want="$1" cmd="$2" cwd="$3"
  local payload
  payload=$(python3 -c 'import json,sys;print(json.dumps({"tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$cwd")
  out=$(printf '%s' "$payload" | "$HOOK" 2>&1); got=$?
  local mark="ok  "
  if [ "$got" != "$want" ]; then mark="FAIL"; fails=$((fails+1)); fi
  printf '[%s] want=%s got=%s | %-46s | %s\n' "$mark" "$want" "$got" "$cmd" "$out"
}

echo "--- force push: always BLOCKED (exit 2) ---"
run 2 'git push --force origin main'          "$PERSONAL"
run 2 'git push -f origin feature/leo/x'      "$WORK"
run 2 'git push origin main -f'               "$PERSONAL"
run 2 'git -C ~/src/x push -f'                "$PERSONAL"

echo "--- personal repo (working-agent): main OK, master/staging BLOCKED ---"
run 0 'git push origin main'                  "$PERSONAL"
run 0 'git push -u origin main'               "$PERSONAL"
run 2 'git push origin master'                "$PERSONAL"
run 2 'git push origin staging'               "$PERSONAL"

echo "--- work repo (emr-v2): main/master/staging BLOCKED, feature/bugfix OK ---"
run 2 'git push origin main'                  "$WORK"
run 2 'git push -u origin main'               "$WORK"
run 2 'git push origin staging'               "$WORK"
run 2 'git push origin stage_test'            "$WORK"   # not a protected name -> see note below
run 0 'git push -u origin bugfix/leo/x'       "$WORK"
run 0 'git push origin feature/leo/vp-1'      "$WORK"

echo "--- cd <path> && push: policy follows the cd target, not the session cwd ---"
run 2 'cd '"$WORK"' && git push origin main'  "$PERSONAL"
run 0 'cd '"$PERSONAL"' && git push origin main' "$WORK"

echo "--- unidentified repo: default STRICT (main blocked) ---"
run 2 'git push origin main'                  "/nonexistent/dir"

echo "--- non-push commands: ALLOWED ---"
run 0 'rm -f tmp.js'                          "$PERSONAL"
run 0 'tail -f logs/app.log'                  "$PERSONAL"
run 0 'grep -f pats file'                     "$PERSONAL"
run 0 'rm -f a.js && git push origin main'    "$PERSONAL"

echo
if [ "$fails" -eq 0 ]; then echo "ALL PASS"; else echo "$fails FAILED"; exit 1; fi
