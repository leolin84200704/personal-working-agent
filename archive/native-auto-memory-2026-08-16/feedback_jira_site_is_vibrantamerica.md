---
name: jira-site-is-vibrantamerica
description: "SOLVED 2026-07-31 + reload gap closed 2026-08-03: wrong zymebalanz.atlassian.net links came from a WezTerm hyperlink_rule in ~/.wezterm-local.lua; the file fix did NOT reach the running WezTerm because dofile'd files aren't auto-reload-watched — touch the main config (or restart WezTerm) after editing it"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 688dadef-f027-4f6d-af1d-07376d10c5af
  modified: 2026-08-03T17:41:20.229Z
---

The Jira site for VP/LBS/QH tickets is `https://vibrantamerica.atlassian.net/browse/{KEY}`. Leo's
login email domain is zymebalanz.com, which is NOT the Jira site.

**Root cause (found 2026-07-31 by grepping my own session transcripts, not repo files).** Leo saw
wrong links three times (2026-07-20, 07-21, 07-31) even though my emitted text was correct — on
07-31 the transcript proved the string `zymebalanz.atlassian.net` appeared in that session only
inside memory-file reads and Leo's own message, never in an assistant text block. The corruption was
downstream of me: a **WezTerm hyperlink rule** that turns every `VP-\d+` on screen into a clickable
link, written by an agent session on 2026-07-09 with the domain guessed from Leo's email:

```lua
-- ~/.wezterm-local.lua  (deliberately NOT tracked in the dotfiles repo)
regex  = '\\b(VP-\\d+)\\b',
format = 'https://zymebalanz.atlassian.net/browse/$1',
```

That file being untracked is why every previous grep "confirmed no such URL exists" — the searches
covered repo files, `~/.config`, `~/.zshrc`, `~/.wezterm.lua`, but never `~/.wezterm-local.lua`.

**Fixed at source** on 2026-07-31: domain corrected to vibrantamerica and the pattern widened to
`(?:VP|LBS|QH)-\d+`, with a comment explaining the trap.

**2026-08-03 recurrence — the fix never reached the running WezTerm.** "WezTerm reloads config
automatically" was wrong for this file: `~/.wezterm-local.lua` is loaded via
`pcall(dofile, ...)` in `~/dotfiles/wezterm/wezterm.lua:74`, and dofile'd files are NOT on
WezTerm's config-reload watch list. The GUI process (started 2026-07-22) kept the old zymebalanz
rule in memory for 4 more days after the file was fixed. Remedy: `touch
~/dotfiles/wezterm/wezterm.lua` (the main config IS watched) or restart WezTerm. Durable option
(not yet applied, dotfiles repo is Leo's): add
`wezterm.add_to_config_reload_watch_list(wezterm.home_dir .. '/.wezterm-local.lua')` to the main
config so future edits to the local file auto-reload.

**Lessons that generalise beyond this bug:**

1. When output "looks wrong" but my text was right, the corruption is in the *display layer* — go
   find it. Grep the **session transcripts** (`~/.claude/projects/<slug>/*.jsonl`, parse the JSONL
   and separate assistant `text` blocks from `tool_use` / `tool_result`) to prove whether I emitted
   it, then hunt the renderer. Do not settle for "probably render-time" as I did for 10 days.
2. A grep that finds nothing proves only that the search space was wrong. State the search space.
3. **Never derive an org's URL from the user's email domain.** That single guess in 2026-07-09 cost
   three interruptions and a wrong remediation.
4. My interim remedy — "stop hyperlinking, write bare keys" — was actively counterproductive: bare
   keys are exactly what the terminal rule matches. Writing `[VP-1234](correct-url)` is fine and
   remains the preferred format ([[always-share-pr-link]] for GitHub links).

cloudId for Atlassian MCP calls: 373c4f18-fda5-4843-8438-6db1ac2e98f0.
