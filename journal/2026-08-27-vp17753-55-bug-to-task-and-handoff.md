---
date: 2026-08-27
slug: vp17753-55-bug-to-task-and-handoff
related:
- VP-17753
- VP-17754
- VP-17755
- VP-9299
distilled: true
---

# VP-17753/54/55 — Bug→Task 更正、三票分析與動工、共用 checkout 事故與交接

## 起點

Leo 問：「VP-17755 / VP-17754 / VP-17753 是什麼 bug？為什麼會以 bug 的形式呈現？
以前不是說這類要改成 task 嗎？有什麼我們現在能做的嗎」

三張是 VP-9299（08-18）辯論挖出的 setting-consumer 缺陷，當時 Leo 裁決只開票。
開票時直接開成 Bug——違反 2026-08-06 規則（未經 Leo 確認不得開 Bug；規則早於開票日，
是當時 session 的疏失，journal/STM 皆無 Leo 核准紀錄）。誠實回報疏失後 Leo 選擇：
三張改 Task（REST PUT issuetype 完成並驗證）+ 三張都動工 + 單 branch 多斷點 commit。

## 分析期的兩個翻轉（反方 subagent 的功勞）

1. **VP-17754 修法反轉**：ticket 原建議「else 分支尊重 options」，但 Azure Event Hubs
   caps session.timeout.ms at 300000 —— caller 要的 950000 傳下去會被 broker 拒 JoinGroup。
   加上 kafkajs 無背景 heartbeat（heartbeat 參數全檔零呼叫）、45s 是 prod 實際運作值，
   修法變成「刪掉謊言」：移除 options 參數與三個 950000 引數。真正根治慢訊息的是
   17753 的 axios timeout。
2. **VP-17755 修法反轉**：ticket 原建議二選一，反方三刀砍死「恢復 writer」：
   syntheticSuccess 讓 errorCode==0 不可當成功判準；24h per-sample key 會壓掉合法的
   多次 finalize 通知；check 與 write 相隔 500 行（中含 5s sleep）×3 replicas 的 race。
   prod 量測（trigger_history 30 天）：16,578 sample 僅 18 個 >1 event、24h 內僅 1 ——
   gate 每月只擋 ~1 封重複信。結論：刪 gate。

VP-17753 維持 fail-open（view_report_link 是 payload，product list 是裝飾），加上
ENGINEERING-LESSONS「fail-open 要可數」：降級送信寫 failed_notification（查證過此表
只有 writer 沒有自動 retry reader，不會重寄）。

## 事故：共用 checkout 的 `git add -A`

Leo 同時開著互動 session（vibrant-america-working-agent-8d）在同一份
~/src/LIS-setting-consumer checkout 工作：kill 掉我掛住的 jest（spec 缺
'../redis-sentinal' mock）、補 mock、親手做了 17755 的 gate 移除。我的
commit 2 用 `git add -A`，把他 working tree 上的 17755 編輯一起掃進 [VP-17753]
61e6e70 —— 破壞「一票一斷點 commit」。對方 session 隨後 cross-session 叫停，
branch 重整由他們接手；我交接了 Event Hub 上限依據、prod 量測數據、
syntheticSuccess 發現與未辦散件（Postmark 空 product_list 渲染、孤兒
report_email_tokens、sibling 死 gate）。

## 值得記住

- **共用 checkout 不是自己的**：staging 必須點名檔案，commit 前用 git status 對照
  自己動過的檔案清單。異常訊號其實早就出現——spec 檔「被人改了」、HEAD 多了一顆
  不是我下的 commit——當下解讀成「Leo 順手幫忙」，沒有升級成「有另一個 actor 在同一
  份 tree 工作，我的全量 staging 有風險」。
- **Explore 當反方真的會翻案**：兩張票的 ticket 原建議都被推翻，翻案依據（broker 上限、
  syntheticSuccess、race 窗口）全是讀碼讀出來的，不是意見。
- 可攜 lesson 候選（factory）：「Never `git add -A` in a checkout you do not exclusively
  own — stage by explicit path and diff your own change list before committing.」
  待 dream/retrospective 蒸餾成 lesson PR。
