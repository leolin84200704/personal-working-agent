---
name: emr-v2-git-hooks-enforce-iron-rules
description: "lis-backend-emr-v2 local git hooks now machine-enforce 3 IRON RULES (config-yaml-coupling, no-chinese-in-code, build-before-push) — not just memory-based self-discipline"
metadata: 
  node_type: memory
  type: project
  originSessionId: a19bcf1c-546a-4254-9b0b-46068382ee68
---

`lis-backend-emr-v2/.git/hooks/` 自 2026-06-26 起有兩個 hook，把長期重犯的 IRON RULE 從「靠自覺」升級為「git 機器強制」。hook 在 `.git/hooks/`（**不進版控，repo 瀏覽看不到**；重新 clone 不會帶過去；worktree 共用主 repo hooks 所以涵蓋）。全部可 `--no-verify` 故意略過。

**pre-commit**（兩個 guard 並存）:
- guard 1 `config-yaml-coupling`: staged 新增的 `process.env.X`（字面形式，未涵蓋解構/ConfigService.get，刻意先不擴）若不在 BOTH `lis-emr-v2-config.yaml` + `lis-emr-v2-config-prod.yaml` 的 `data:` → 擋 commit。對應 [[config_yaml_coupling_with_code]]（INCIDENT-20260601 重犯 3 次）。
- guard 2 `no-chinese-in-code`: staged 新增 `.ts/.js/.sql` 行含 CJK（perl `-CSD`，BSD grep 無 `-P`）→ 擋。對應 [[no_chinese_in_code]]。markdown/docs 不查。

**pre-push** `start:dev iron rule`: push 前跑 `npx prisma generate` + `npm run build`(=nest build)，任一失敗擋 push。對應 [[start_dev_iron_rule]]（VP-16521 切 branch 沒 prisma generate）。log 在 /tmp/emr-v2-prepush-*.log。

**skillsmp 週掃（雲端→本地改版）**：原 cloud routine `trig_01PLD8qERLCgc5NMQ7uggHDL` 已 **disabled**（Leo 嫌雲端要自己去頁面看、無 man-in-loop），改成本地：`~/.claude/hooks/skillsmp-reminder.sh`（UserPromptSubmit hook，已註冊在 `~/.claude/settings.json`）在**週二/週五早上(<12:00 LA)**第一次發 prompt 時注入提醒，state 檔 `~/.claude/.skillsmp-reminder.last` 做每日去重 → Claude 主動問 Leo 要不要當場用 WebSearch/WebFetch 跑掃描並討論。硬篩 vibe-coder/前端/autonomous。

**skill-creator + 自製 skill（2026-06-26）**：裝了 anthropics `skill-creator`（`~/.claude/skills/skill-creator/`）。用它的撰寫標準（非跑 eval harness——主觀/reference 型 skill 跳過量化 benchmark）做了 3 個 global skill：`emr-order-customer-resolution`（ehr_integrations winner 邏輯 + emr_code_not_found debug，內容源自 [[reference_emr_v2_order_customer_resolution]]）、`lis-prod-change-gate`（prod 變更 9 道 gate，蒐集所有 prod-safety 鐵則，含指向上面 git hooks）、`ticket-requirements-clarify`（需求模糊時多輪澄清 + 草擬英文 PM Jira comment，取代裝 obra/superpowers——整套 TDD/autonomous 與鐵則衝突故不裝）。

**markitdown CLI + skill**：`pipx install markitdown[pdf,docx,pptx,xlsx,xls]`（v0.1.6, Python 3.14, binary `~/.local/bin/markitdown`，`pipx ensurepath` 已加 PATH）。skill `~/.claude/skills/ticket-attachment-to-md/`：ticket 附件 PDF/Excel/CSV/Word/PPT→markitdown 轉 md；PNG/JPG→直接 Read（Claude 原生視覺，markitdown 對圖只給 EXIF）。刻意用 CLI 非 MCP（偶爾用、不養常駐 server）。
