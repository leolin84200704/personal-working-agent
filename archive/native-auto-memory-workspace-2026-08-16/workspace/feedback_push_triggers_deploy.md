---
name: push-triggers-deploy
description: "lis-backend-emr-v2 deploy 路徑：feature/bugfix branch push 不會 auto-deploy。要 deploy → 開 PR target staging（不准 git push staging）。main 絕對不准動。驗證 2026-06-04：feature branch push 兩次 prod pod uptime 不變"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 37705de5-a5b9-4549-b1be-2b522e1b4b48
---

# 規則（2026-06-04 Leo 強調）

Leo 原話：「以後你要 push 要 push 到 staging 不能直接 push 到 main」

實際操作分流（與 [[feedback-no-direct-push-to-staging]] 一致）：

| 動作 | 目標 | 副作用 | 我能做嗎 |
|---|---|---|---|
| `git push origin bugfix/leo/{ticket}` | feature/bugfix branch | 純存 code，不 deploy | ✅ 可以，Leo 同 turn 授權即可 |
| `gh pr create --base staging --head bugfix/leo/...` | PR to staging | 等 Leo 找人 approve+merge → staging env deploy | ✅ 可以開 PR |
| `git push origin staging` | staging branch | 直接 deploy staging 沒 review | ❌ **不准**（per [[feedback-no-direct-push-to-staging]]） |
| `git push origin main` | main branch | 直接 deploy prod 沒任何 gate | ❌ **絕對不准** |

## How to apply

- 改完 code → push 自己的 `bugfix/leo/{ticket}` branch（OK）
- 要進 staging 驗證 → **`gh pr create --base staging`**，等 Leo / reviewer merge
- 進 prod 不是我的事 — Leo 或 release process 自己處理 staging → main
- 同 turn「commit + push」授權只覆蓋自己 branch；要開 PR / 跨 branch action 都要再確認

## Why 之前那個 memory 寫錯

舊版本 memory 寫「push 任何 branch = Jenkins auto-build + prod rollout restart」是不對的。
今天驗證：
- 同 session push `bugfix/leo/INCIDENT-20260604-mdhq-leak` × 2 commit
- prod pod `lis-emr-v2-deployment-prod-64c979d669-v7r5m` uptime 仍 27h，沒被 restart

正確：Jenkins 對 feature branch 不 auto-deploy。Auto-deploy hook 應該掛在 `staging` 和 `main` 上。
舊 memory 的 INCIDENT-20260601 4 commit 全部觸發 deploy 那段——可能 Jenkinsfile 後來改了，或那 4 個 commit 是 push 到 staging/main 不是 feature branch（要 audit history 才能確定，但 forward-looking 採今天的觀察）。

## CLAUDE.md 衝突

`/Users/hung.l/src/CLAUDE.md` 寫「禁止: push to main/master/staging」這條跟 [[feedback-no-direct-push-to-staging]] 一致（兩個都禁止 staging git push）。Leo 口頭「要 push 到 staging」實際意思是「PR target staging」不是字面 git push。

## 同類前科

- [[config-yaml-coupling-with-code]]：env-driven code 改了沒主動同步 YAML
- [[feedback-no-direct-push-to-staging]]：同一條規則的另一個 framing
- 共通：我把「允許 X」字面解讀過寬，沒分清「git 操作允許」vs「business 工作流允許」
