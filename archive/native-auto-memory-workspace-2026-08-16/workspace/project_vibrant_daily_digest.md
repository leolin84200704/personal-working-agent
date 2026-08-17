---
name: project_vibrant_daily_digest
description: launchd nightly job summarizing Vibrant-America commits + Jira VP; as of 2026-07-02 pushes the digest straight to lis-code-agent main (was auto/daily-digest)
metadata: 
  node_type: memory
  type: project
  originSessionId: 7002deea-85f4-4fad-a683-0200f9076537
---

每晚本地 00:00 的 launchd job「Vibrant America Daily Digest」(設於 2026-06-23)。

- **機制**: macOS launchd `~/Library/LaunchAgents/com.lis.vibrant-daily-digest.plist`,本地時間 00:00(自動處理 DST,無 UTC 漂移),`RunAtLoad=false`。雲端 routine 行不通(雲端沙箱無 Leo 憑證、private repo 讀不到、push 需 GitHub App,Leo 改用本機)。
- **隔離**: 跑在 git worktree `/Users/hung.l/.lis-daily-digest/main`,**絕不在** Leo 的工作 repo `/Users/hung.l/src/lis-code-agent` 跑。worktree 為 **detached HEAD**(2026-07-02 起無具名 branch;`auto/daily-digest` 已刪),每次 run `git checkout --detach origin/main` 重新對齊最新 main。
- **內容**: headless `claude -p --dangerously-skip-permissions` 讀 prompt `scripts/daily-digest-prompt.md` → `gh api` 列 Vibrant-America org 今日 commits(唯讀)+ Atlassian MCP 查 `project=VP AND updated>=startOfDay()` → 寫 `long-term-memory/daily-digest/<DATE>.md`(繁中,**不碰**精修 knowledge 檔)→ commit+push。
- **push 目標 = `main`(2026-07-02 改)**: 原本推 `auto/daily-digest` 且 hook 擋 main。Leo 決定 digest 直接進 main:(1) 舊的 5 份 digest 檔 + job scripts 從 `auto/daily-digest`(長在舊 base) 整併進 main 並 push(commit `0634774`);(2) 放寬 `.claude/hooks/validate-git-push.sh` 允許 push main(保留 force-push + `master/staging` + `reset --hard` 封鎖),CLAUDE.md git 規則加「僅本 personal repo 允許 push main」例外;(3) prompt step6:`git fetch` → `git checkout --detach origin/main` → 加當日 digest → `git push origin HEAD:main`(FF);(4) 刪除 remote `origin/auto/daily-digest` + 所有相關 local branch(`auto/daily-digest`、`backup/main-e38ce56`、`backup/auto-daily-digest`、`feature/leo/agent-improve-fac`),worktree 改 detached HEAD。lis-code-agent local 現只剩 `main`。見 [[feedback_no_direct_push_to_staging]](該規則不適用本 repo)。
- **log**: `/Users/hung.l/.lis-daily-digest/main/logs/daily-digest/*.log`(gitignored)。
- **半夜睡眠坑(已修)**: 2026-06-24 首夜失敗——機器睡著,剛喚醒時 (a) 網路未起→claude `ConnectionRefused`,(b) keychain 鎖住→`gh` token invalid。修法已 push:script 加網路等待(最多 5 分)、`caffeinate -i` 防睡、`GH_TOKEN` 從 `~/.lis-daily-digest/.gh_token`(0600,`gh auth token` 匯出,免 keychain;gh api + git push 都吃此 env)、claude 失敗重試 1 次。`gh` 若重登致 token 輪替,重跑 `gh auth token > ~/.lis-daily-digest/.gh_token`。
- **喚醒排程(已設)**: `sudo pmset repeat wakeorpoweron MTWRFSU 23:58:00`(Leo 2026-06-25 已跑,`pmset -g sched` 確認 wakepoweron 23:58 every day)。午夜需接電源,電池+闔蓋可能不醒→漏跑該夜。
- **待辦**: Atlassian connector SSE endpoint `mcp.atlassian.com/v1/sse` 於 2026-06-30 後停用,需改 Streamable HTTP `/v1/mcp`,否則 digest 的 Jira 區段失效(code 區段不受影響)。
- **前置**: 本機 `gh`(leolin84200704, repo+read:org)讀得到 Vibrant-America;Atlassian MCP 已連。digest 只掃預設分支(feature/staging commit 不涵蓋,缺口區有註明)。
