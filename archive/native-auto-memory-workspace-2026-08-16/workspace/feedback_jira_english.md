---
name: feedback_jira_english
description: "write Jira ticket content (title + description) in English, not Traditional Chinese"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 99dcff7b-017c-4aa9-b3ee-802733ba4be2
---

Jira ticket 內容（summary + description）用**英文**寫，不要繁體中文。

**Why:** Leo 2026-06-25 (VP-17217)：「VP-17217 要改英文的」——我用 zh-TW 寫了 description，被要求改回英文。Jira 是跨團隊共享（PM/reporter 如 Xiaoye Li 等），英文是團隊標準。

**How to apply:** createJiraIssue / editJiraIssue 的 summary + description 一律英文（程式碼、commit、PR 本就英文 [[feedback_no_chinese_in_code]]）。對 **Leo 的對話回覆仍用繁中**。仍遵守 [[feedback_jira_comment]]（comment 先給 Leo 過、不直接 post）。
