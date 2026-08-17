---
name: Jira comment approval
description: Never post Jira comments directly — draft for Leo to review and post himself
type: feedback
originSessionId: 02a26321-ab4a-4c25-8b9b-e103083f0274
---
不要直接用 Atlassian MCP 發 Jira comment。先把 comment 內容寫出來給 Leo 看，由他自己決定是否發送和何時發送。

**Why:** Leo 要控制對外溝通的內容和時機。
**How to apply:** 所有 addCommentToJiraIssue、createJiraIssue、editJiraIssue 等寫入操作都先草稿給 Leo，不直接執行。
