---
name: feedback-tool-notice-filtering
description: "Don't blindly forward tool-emitted notices/warnings to the user; first verify it is actionable by THIS user"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e78e7f19-dcbb-4fd1-b53c-f44060c07bd3
---

Never auto-forward generic notices, deprecation warnings, or SDK migration
hints emitted in tool results without first verifying they are actionable by
*this* user given *their* config. Many of these messages are written for SDK
implementors or backend operators, not Claude Code end users.

**Why:** during VP-16629 work I forwarded the Atlassian MCP HTTP+SSE → Streamable HTTP
deprecation message (`https://mcp.atlassian.com/v1/sse` → `https://mcp.atlassian.com/v1/mcp`,
2026-06-30) four times across consecutive Confluence updates. Leo eventually
asked "if it's a backend problem why are you asking me to fix it?" — the
notice belonged to claude.ai's managed connector (the `claude.ai Atlassian`
prefix is a backend-managed broker, evidenced by `claudeAiMcpEverConnected`
in `~/.claude.json` and the fact that `claude mcp remove` reports no such
local server). Leo can't change it; Anthropic / Atlassian will migrate the
broker before the deprecation date. Forwarding the notice each time wasted
his attention and read as if I was asking him to do something.

**How to apply:**
1. When a tool result contains a `[IMPORTANT: ...]` or deprecation banner,
   pause before relaying it.
2. Check whether the resource it references is in user-managed config
   (`~/.claude/mcp.json`, `~/.claude.json` `mcpServers`, project `.mcp.json`,
   or `claude mcp list` user-scope servers). If not present there, it is
   almost certainly backend-managed and the user has nothing to do.
3. If actionable by the user → surface once with a one-line explanation of
   what to change. If not actionable → omit entirely (do not even footnote);
   the user did not opt into reading SDK changelogs.
4. Same rule applies to other tool-emitted banners: rate-limit warnings
   only matter if the user can adjust the call site; library deprecation
   notices only matter if the user owns the dependency declaration.
