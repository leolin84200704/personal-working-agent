---
name: feedback-skill-desc-optimization
description: "When creating/finalizing a skill, remember skill-creator's description-optimization loop exists and proactively ask Leo whether to run it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a19bcf1c-546a-4254-9b0b-46068382ee68
---

skill-creator 內建一個 description 自動優化迴圈（`~/.claude/skills/skill-creator/scripts/run_loop.py`，背景跑 `claude -p` 測觸發準度，~5 輪，選 held-out test 分數最高的 description）。Leo 指示：**「你要記得有這個東西，每次檢查我是不是該跑。」**

**Why:** skill 的 description 是觸發的唯一機制；寫得不好會 under-trigger（該用時沒用）或亂觸發。但每次都自動跑又是 over-engineering（違反 [[feedback_pursue_cleaner_design]] 的隱性成本意識）。

**How to apply:** 定稿一個 skill、或事後發現某 skill 該觸發沒觸發/亂觸發時，主動問 Leo 要不要對那個 skill 跑優化迴圈。草稿階段或小編輯就略過。已加 PostToolUse hook `~/.claude/hooks/skill-desc-opt-reminder.sh`（動到 `*/SKILL.md` 時注入提醒）當機器 backstop，見 [[project_emr_v2_git_hooks]]。不要每次都跑，judgment call。
