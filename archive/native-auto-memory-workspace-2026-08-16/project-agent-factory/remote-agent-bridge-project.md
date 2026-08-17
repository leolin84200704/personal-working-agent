---
name: remote-agent-bridge-project
description: Leo 的個人專案 remote-agent-bridge（手機操控電腦 agent），workspace 在 ~/personal/remote-agent/，2026-07-25 完整 bootstrap
metadata: 
  node_type: memory
  type: project
  originSessionId: 2c8f3386-f773-43c9-a4f5-2477def3141b
  modified: 2026-07-25T23:45:43.938Z
---

Leo 的**個人專案**（與 Vibrant America 工作無關）：remote-agent-bridge — 用手機操控電腦上的 agent（指派工作、確認回覆），解決現有 phone↔computer 連線/驗證流程繁瑣的問題。

- Workspace：`~/personal/remote-agent/`（2026-07-25 從 ~/src 搬出，避免載入 Vibrant 的父目錄 CLAUDE.md）；instance repo `remote-agent-bridge-agent/`（memory + CLAUDE.md），產品 repo `remote-agent-bridge/`（greenfield，只有 README，tech stack 未定）
- 2026-07-25 依 BOOTSTRAP.md 完整 bootstrap：STM/journal/LTM/archive + dream pipeline（GitHub Issues reconcile 版，launchd 未安裝，手動 run-dream.sh，排程模板 19:30 與 LIS 18:30 錯開）
- GitHub（private，帳號 `leolin84200704`）：`remote-agent-bridge`（issues 開這裡）、`remote-agent-bridge-agent`
- 設計已定案（2026-07-25，詳見 instance 的 `long-term-memory/product-design.md`）：Tailscale 傳輸（relay 留 v2）、native iOS app、Node/TS daemon + Claude Agent SDK、互動式 session、tailnet+配對 token 驗證、MVP 單一可撤銷 scope
- 產品 repo PR #1（git safety hooks）等 Leo merge；下一步是拆 MVP milestone 開 GitHub issues

相關：[[personal-project-not-vibrant-framework]]
