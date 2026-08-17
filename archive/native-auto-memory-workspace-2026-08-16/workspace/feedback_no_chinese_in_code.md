---
name: feedback-no-chinese-in-code
description: All code and code comments must be English-only; no Chinese in source
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd572592-84d4-40cc-b380-44631eaf282a
---

All code and code comments (and DDL/migration files) committed to LIS repos must be **English only** — no Chinese characters anywhere in source or comments. Replies to Leo stay Traditional Chinese, and agent memory/STM can be Chinese, but anything that lands in a repo (identifiers, comments, log strings, migration SQL comments) must be English.

**Why:** Code is shared with other engineers and reviewed in PRs; mixed-language comments are not acceptable in the codebase.

**How to apply:** Before committing, grep changed files for CJK characters and rewrite any Chinese comments/strings in English. Applies to VP-16859 deep-link work (schema comments, controller comments, migration SQL) and all future code. Related: [[feedback_no_direct_push_to_staging]]
