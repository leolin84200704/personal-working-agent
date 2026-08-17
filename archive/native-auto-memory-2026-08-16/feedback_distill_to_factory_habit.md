---
name: distill-to-factory-habit
description: "After any work item, proactively push agent-repo changes AND check for portable lessons to distill into project-agent-factory via lesson PRs — without being asked"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1fbf0ab5-509e-4a5d-9189-cb6953f4c5cc
---

Leo (2026-07-14, VP-17412): 「把你的改動也要推到vibrant agent, 並看看有沒有可以distill到agent factory的(這應該是要養成習慣的...不知道為什麼你沒有做)」

**Why:** The factory only stays alive if every instance feeds portable lessons back; skipping the check silently degrades it into a dead document. Leo had to point this out after I finished VP-17412 without distilling.

**How to apply:** At the end of each work item: (1) commit/push all vibrant-agent repo changes (automation behavior → PR, data/STM → direct main); (2) run the factory-distillation check now codified as WORK-LOOP Step 8 item 6 — if a lesson holds after removing company/system names AND would recur in a different job, open a lesson PR per CONTRIBUTING.md (one lesson per PR, branch `lesson/lis/{slug}`, de-identified file content, specifics in PR body); if nothing is portable, say so explicitly. Note: watch-prompt/cron canonical copies live in `DailyJob/watch_prompts/` in the INSTANCE repo, not the factory ([[repo-placement]] — instance-specific vs portable).
