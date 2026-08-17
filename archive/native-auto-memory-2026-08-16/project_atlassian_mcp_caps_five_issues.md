---
name: project_atlassian_mcp_caps_five_issues
description: "Atlassian MCP JQL search returns at most 5 issues with no page token; use Jira REST for bulk enumeration, changelogs, and comments"
metadata: 
  node_type: memory
  type: project
  originSessionId: 504f8dcd-e280-4af7-a0b0-cd3657b23ebd
  modified: 2026-08-13T07:06:43.921Z
---

`mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql` returns **at most 5 issues** regardless of `maxResults`, reporting the rest as `remainingCount` with `pageInfo.hasNextPage: false` and **no `endCursor`** — so it cannot be paginated. Trimming the `fields` list does not raise the cap (`summary` and `description` come back even when not requested).

For anything needing the full result set (daily digests, "all tickets updated today", per-ticket transitions), go straight to the Jira REST API:

```
EMAIL=$(grep -m1 -oE '[A-Za-z._-]+@[A-Za-z.-]+' ~/src/credential/atlassian-api-token.md)
TOKEN=$(grep -m1 '^token:' ~/src/credential/atlassian-api-token.md | sed 's/^token:[[:space:]]*//')
curl -s -u "$EMAIL:$TOKEN" -G "https://vibrantamerica.atlassian.net/rest/api/3/search/jql" \
  --data-urlencode 'jql=project = VP AND updated >= "2026-08-12 00:00" AND updated < "2026-08-13 00:00"' \
  --data-urlencode 'maxResults=100' \
  --data-urlencode 'fields=key,summary,status,assignee,issuetype,created,updated,priority' \
  --data-urlencode 'expand=changelog'
```

`expand=changelog` is what makes real status transitions (who moved what, when) visible — without it you only have current status plus an `updated` timestamp, which is not enough to say what changed. Add `fields=comment` to get comments in the same call.

**Why it matters beyond convenience:** the `updated` count is misleading on its own. On 2026-08-12, 17 of 50 "updated" VP tickets had only `Automation for Jira` writing `Duration`/`Start date` at 09:00 — 34% automation noise. Only the changelog distinguishes that from human activity.

Credentials: `~/src/credential/atlassian-api-token.md` (HTTP Basic, email + token). Related: [[feedback_never_report_atlassian_mcp_sse_notice]].
