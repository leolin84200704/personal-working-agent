#!/bin/bash
# PreToolUse guard on `git commit`: staged NON-markdown files must not
# introduce CJK text. Deterministic enforcement (ENFORCEMENT-LADDER.md tier 5)
# of the AGENTS.md rule "code, comments, commit content in English" — the
# prose rule alone decays with session length.
#
# Scope is deliberately narrow: markdown/docs are exempt. A doc's language
# follows the repo owner's convention, which is a human judgment (the
# ask-first rule: personal repo -> owner decides; team repo -> the team must
# accept the convention). Code files carry no such discretion.
#
# Pauses once per session+repo (exit 2); a justified retry passes — CJK can
# be legitimate (i18n resources, test fixtures), so this reminds, not forbids.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
SESSION=$(echo "$INPUT" | jq -r '.session_id // "nosession"')
[ -z "$COMMAND" ] && exit 0
echo "$COMMAND" | grep -qE 'git[^;|&]*\bcommit\b' || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

HIT=$(git diff --cached -- . ':(exclude)*.md' 2>/dev/null | \
  perl -CSD -ne 'if (/^\+/ && !/^\+\+\+/ && /[\x{4E00}-\x{9FFF}\x{3040}-\x{30FF}\x{AC00}-\x{D7AF}]/) { print; exit 0 } END { exit 1 }')
[ -z "$HIT" ] && exit 0

REPO_KEY=$(git rev-parse --show-toplevel 2>/dev/null | shasum | cut -c1-12)
MARKER="${TMPDIR:-/tmp}/repo-lang-ok-${SESSION}-${REPO_KEY}"
[ -f "$MARKER" ] && exit 0
touch "$MARKER"

cat >&2 <<EOF
PAUSED (once per repo per session): this commit stages CJK text in a
NON-markdown file, e.g.:
  ${HIT}
Code, comments, and commit content stay in English (AGENTS.md). If the CJK
is intentional (i18n resource, test fixture, user-facing string the repo
already carries), state that and re-run the commit — it will pass.
Otherwise translate or unstage the offending hunk first.
EOF
exit 2
