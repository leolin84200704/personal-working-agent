#!/bin/bash
# Validate git push commands — block force push and push to protected branches.
# Called by Claude Code PreToolUse hook. Receives JSON on stdin.
#
# Protected-branch policy is REPO-AWARE and fail-safe:
#   - personal repos (vibrant-america-working-agent, project-agent-factory):
#       `main` is allowed (daily-digest / knowledge consolidation land there);
#       master/staging/develop blocked.
#   - every other repo (emr-v2 and all Vibrant work repos):
#       main/master/staging/develop ALL blocked — the agent may only push
#       feature/leo|bugfix/leo branches; promotion goes through a PR.
#   - if the target repo cannot be identified, default to the STRICT (work-repo) policy.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
[ -z "$COMMAND" ] && exit 0

# Block force push. The force flag must be scoped to the push command itself:
# a bare `-f ` anywhere used to block ordinary calls like `rm -f tmp.js`,
# `tail -f log`, `grep -f patterns` (hit twice during the 2026-07-29 dream run).
# `[^;&|]*` keeps the match inside the same command segment, so
# `rm -f x && git push` is not treated as a force push.
if echo "$COMMAND" | grep -qE 'push[^;&|]*(--force|[[:space:]]-f([[:space:]]|$))'; then
  echo "BLOCKED: force push 不允許。" >&2
  exit 2
fi

# Resolve the effective repo directory for this push.
# Priority: `git -C <path>` in the command > a leading `cd <path> &&` > session cwd.
REPO_DIR=$(echo "$COMMAND" | grep -oE 'git[[:space:]]+-C[[:space:]]+[^[:space:]]+' | head -1 | awk '{print $3}')
if [ -z "$REPO_DIR" ]; then
  REPO_DIR=$(echo "$COMMAND" | grep -oE '(^|&&|;)[[:space:]]*cd[[:space:]]+[^[:space:]]+' | head -1 | awk '{print $NF}')
fi
[ -z "$REPO_DIR" ] && REPO_DIR="$CWD"
REPO_DIR="${REPO_DIR/#\~/$HOME}"   # expand a leading ~

ORIGIN=$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null)

# Protected-branch match: tolerant of flags/remote between `push` and the branch
# (so `git push -u origin main` is caught, not just `git push origin main`).
# The leading \s+ anchors the branch as its own token, so `release/main` is not matched.
PERSONAL_BLOCK='push([[:space:]]+[^[:space:]]+)*[[:space:]]+(master|staging|develop)([[:space:]]|$|:)'
WORKREPO_BLOCK='push([[:space:]]+[^[:space:]]+)*[[:space:]]+(main|master|staging|stage_test|develop)([[:space:]]|$|:)'

if echo "$ORIGIN" | grep -qE 'vibrant-america-working-agent|project-agent-factory'; then
  # Personal repo: main allowed, master/staging/develop blocked.
  if echo "$COMMAND" | grep -qE "$PERSONAL_BLOCK"; then
    echo "BLOCKED: 不能直接 push 到 master/staging/develop。" >&2
    exit 2
  fi
else
  # Work repo (or unidentified target): main/master/staging/develop all blocked.
  if echo "$COMMAND" | grep -qE "$WORKREPO_BLOCK"; then
    echo "BLOCKED: 工作 repo 不允許直接 push main/master/staging（改開 PR，只能 push feature/leo|bugfix/leo 分支）。" >&2
    exit 2
  fi
fi

exit 0
