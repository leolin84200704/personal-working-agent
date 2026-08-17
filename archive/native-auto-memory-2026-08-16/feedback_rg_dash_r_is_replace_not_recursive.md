---
name: feedback-rg-dash-r-is-replace-not-recursive
description: "rg -r is --replace, not recursive; -rn/-ril/-rin silently eat the next letters as the replacement string and disable -i/-l/-n, producing mangled or falsely-empty results"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d2c7498f-5248-41c2-8a77-bb8540f34754
  modified: 2026-08-03T21:37:08.209Z
---

`rg -r` is `--replace`, and it consumes the following characters as its value. So
`rg -rn 'pat' path` means replacement `n`, and `rg -ril 'pat' path` means replacement `il` —
**`-i`, `-l` and `-n` never take effect.** Two failure modes, both silent:

1. **Mangled output.** Matches are printed with the match replaced by the literal value,
   so `slackSend(...)` prints as `ilSend(...)` and "eligibility" prints as "liy". On
   2026-08-03 I misread this as the *terminal display layer* eating characters, and even
   linked it to the WezTerm hyperlink_rule incident ([[feedback_jira_site_is_vibrantamerica]]).
2. **Falsely-empty results.** Losing `-i` makes the search case-sensitive. Searching
   lowercase `slack` in a Java repo returned only `Jenkinsfile`, so I told Leo "Java has no
   application-level Slack sender". With `rg -il` it actually has
   `com/vibrant/emr/notification/Slack.java` plus three call sites. Leo caught it by asking
   "那之前 java code 連到 slack 是用什麼連的呢?" — the third time in one session that this
   flag corrupted a conclusion I had already reported.

**Why:** the mistake never errors. It degrades a search into a different, wrong search, and
the output still looks like a plausible answer.

**How to apply:** write search flags separately and never adjacent to `-r` — `rg -i -l pat`,
`rg -n pat`. Recursion is rg's default; there is no `-r` needed for it (that's grep's `-r`).
Also: rg uses `-g` for globs, not grep's `--include`; a wrong flag plus `2>/dev/null`
turns a tool error into a fake "0 hits". When a search returns nothing or returns text that
looks corrupted, re-run the command verbatim without redirection and confirm the flags before
believing the result — see [[feedback_never_conclude_breakage_from_a_quiet_window]] for the
same failure shape (absence of evidence read as evidence of absence).
