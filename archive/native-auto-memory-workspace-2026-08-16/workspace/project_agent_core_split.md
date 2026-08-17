---
name: project-agent-core-split
description: 2026-07-04 拆層完成 — 個人層在 ~/agent-core（GitHub private repo），lis-code-agent 只剩 Vibrant instance；context 載入鏈與 skills 位置都變了
metadata: 
  node_type: memory
  type: project
  originSessionId: 05448196-4a9c-4f7b-a065-9b5a93e983cf
---

2026-07-04 完成 agent 分層拆分（Leo 要的「可攜個人層 + 可拋棄工作層」架構）：

- **Layer 1 個人層**: `~/agent-core`（github.com/leolin84200704/agent-core, private）。`~/.claude/CLAUDE.md` 是 symlink → `~/agent-core/AGENTS.md`，全域載入。框架（WORK-LOOP/RETRIEVAL/ENGINEERING-LESSONS/templates/BOOTSTRAP）在 `~/agent-core/framework/`，按需讀取不預載。
- **Layer 2 Vibrant instance**: `lis-code-agent/CLAUDE.md` 已瘦身，只剩工作專屬內容並指向 framework。`~/src/CLAUDE.md` 只剩一行 `@lis-code-agent/CLAUDE.md` import — 不要再往裡面加規則。
- **Skills 搬家**: `emr-order-customer-resolution`、`lis-prod-change-gate` 從 `~/.claude/skills` 移到 `lis-code-agent/.claude/skills/`（版控），由 `~/src/.claude/skills/` symlink 供發現；`ticket-requirements-clarify`、`ticket-attachment-to-md` 實體在 `~/agent-core/skills/`，`~/.claude/skills/` 放 symlink。
- **已驗證 (2026-07-04, headless claude -p)**: symlink skills 發現機制正常 — 從 ~/src 啟動看得到全部四個搬家的 skills；從 ~ 啟動只看得到 user-level 的兩個 generic ticket skills，Vibrant skills 正確隔離。
- 通用工程教訓已蒸餾到 `~/agent-core/framework/ENGINEERING-LESSONS.md`；新的可泛化教訓應寫那裡（見 framework RETRIEVAL.md write-back 表），job-specific 留 lis-code-agent LTM。
- 新工作/專案要養新 agent → `~/agent-core/BOOTSTRAP.md`。
