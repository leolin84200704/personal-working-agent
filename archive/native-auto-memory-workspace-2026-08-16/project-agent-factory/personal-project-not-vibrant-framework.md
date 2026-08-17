---
name: personal-project-not-vibrant-framework
description: Leo 的個人專案不套 Vibrant America 工作框架 — factory 框架可用，但 instance 參數（Jira、LIS 規則）不沿用
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2c8f3386-f773-43c9-a4f5-2477def3141b
  modified: 2026-07-25T23:15:00.546Z
---

Leo 澄清（2026-07-25，建 remote-agent-bridge 時）：他的個人專案不適用 Vibrant America 的工作框架。

**Why:** project-agent-factory 是個人可攜框架，Vibrant America 只是其中一個 instance；個人專案是另一個獨立 instance，Jira、LIS work loop 參數、LIS git 規則都不該滲進去。

**How to apply:** 幫 Leo 的個人專案初始化 agent 時，走 BOOTSTRAP.md 但所有 instance 參數重新問/重新定義（ticket 系統偏好 GitHub Issues），不要從 vibrant-america-working-agent 抄設定；CLAUDE.md 裡明寫「不套用 Vibrant instance 規則」。

相關：[[remote-agent-bridge-project]]
