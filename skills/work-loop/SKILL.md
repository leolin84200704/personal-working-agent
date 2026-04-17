---
name: work-loop
description: 完整的 ticket 處理工作流程
trigger: "work loop {ticket_id}" or "處理 ticket {ticket_id}" or "執行 {ticket_id}"
---

# Work Loop - 完整工作流程

## 概述
模仿人類開發者的完整工作流程：理解→辯論→討論→執行→回顧→學習

完整流程共 9 步：
1. **Retrieve** — 檢索過去經驗
2. **Analyze** — 分析理解 ticket
3. **Debate** — 正反辯論方案
4. **Discuss with User** — Man-in-the-loop 確認
5. **Execute** — 執行實作
6. **Review with User** — 使用者 Review
7. **Complete** — 完成收尾
8. **Retrospective** — 回顧反思
9. **Memory Update** — 記憶更新

---

## 初始化

進入 Work Loop 前，先建立追蹤結構：

```
1. stm_create(ticket_id) — 建立短期記憶檔案
2. task_create(title="[{ticket_id}] Work Loop", description="Step 1~9 完整流程")
3. jira_get_ticket(ticket_id) — 取得 ticket 內容
```

將 ticket 內容存入短期記憶：
```
stm_append(ticket_id, section="Ticket Analysis", content="ticket 原始內容摘要...")
```

---

## Step 1: Retrieve（檢索經驗）
**目的**: 在開始前先找過去的相關經驗

**動作**:
1. `stm_search(query="{ticket 的 summary 和關鍵字}")` — 搜尋類似的過去 ticket 經驗
2. `memory_search(query="{相關技術關鍵字}")` — 搜尋相關的長期知識
3. 如果找到相似 ticket，用 `stm_read(ticket_id="{相似ticket}")` 讀取其詳細記錄，特別關注 Failures 區段
4. 如果有高度相似的 ticket，用 `stm_get_failures(ticket_id="{相似ticket}")` 取得失敗紀錄

**記錄**: 將相關發現記到 `stm_append(ticket_id, section="Ticket Analysis", content="過去經驗: ...")`

**進度更新**: `task_update(task_id, status="in_progress", description="Step 1: Retrieve — 檢索過去經驗")`

**暫停條件**: 無，繼續下一步

---

## Step 2: Analyze（分析理解）
**目的**: 深入理解 ticket 需求、影響範圍、相關程式碼

**動作**:
1. 分析 ticket 內容：
   - 提取關鍵資訊（ID、名稱、設定值等）
   - 辨識 ticket 類型（新增、修改、修復、重送等）
   - 確認需求是否清楚，是否需要跟 PM 確認
2. `spawn_agent(agent_type="explore", task="調查 {ticket 相關的程式碼和設定}")` — 探索相關程式碼
   - 搜尋相關 service、config、資料表
   - 確認現有狀態（資料庫記錄、設定檔等）
3. `spawn_agent(agent_type="analyze", task="分析 {ticket_id} 的影響範圍和風險")` — 分析影響範圍
   - 哪些 service 會被影響？
   - 有沒有 side effect？
   - 需要改幾個地方？
4. 根據分析結果，草擬 1~3 個可能的解決方案

**記錄**:
- `stm_append(ticket_id, section="Ticket Analysis", content="需求分析: ...\n影響範圍: ...\n相關程式碼: ...")`
- `stm_append(ticket_id, section="Approaches Considered", content="方案A: ...\n方案B: ...\n方案C: ...")`

**進度更新**: `task_update(task_id, description="Step 2: Analyze — 分析理解完成")`

**暫停條件**:
- 如果需求不清楚 → 暫停，列出需要確認的問題，呈報使用者
- 如果需求清楚 → 繼續下一步

---

## Step 3: Debate（正反辯論）
**目的**: 用正反方辯論確保方案品質

**動作**:
1. `spawn_agent(agent_type="debate_pro", task="為以下方案辯護：{推薦方案}。理由、優點、為什麼這是最好的做法。")` — 正方：為方案辯護
2. `spawn_agent(agent_type="debate_con", task="質疑以下方案：{推薦方案}。風險、缺點、邊界案例、可能的問題。")` — 反方：質疑方案、找風險
3. 綜合雙方論點，調整方案：
   - 如果反方提出了有效風險 → 調整方案或增加防護措施
   - 如果正反方都支持 → 提高信心度
   - 如果有無法解決的風險 → 標記為需要使用者決定

**記錄**: `stm_append(ticket_id, section="Approaches Considered", content="正方: ...\n反方: ...\n結論: ...")`

**進度更新**: `task_update(task_id, description="Step 3: Debate — 正反辯論完成")`

**暫停條件**: 無，繼續下一步

---

## Step 4: Discuss with User（與使用者討論）
**目的**: Man-in-the-loop — 呈現分析結果和方案，等待確認

**動作**:
1. 整理分析結果和方案（含正反論點），格式化呈現：
   ```
   ## Ticket: {ticket_id} - {summary}
   ### 分析摘要
   - 需求: ...
   - 影響範圍: ...
   - 風險: ...

   ### 建議方案
   - 推薦: 方案 A（理由）
   - 替代: 方案 B（適用情境）

   ### 正反論點
   - 正方: ...
   - 反方: ...

   ### 需要確認
   - [ ] 確認需求理解正確
   - [ ] 確認方案方向
   - [ ] 其他需要釐清的問題
   ```
2. 呈現給使用者
3. **等待使用者回應**（不要自行繼續）
4. 記錄使用者 feedback

**記錄**: `stm_append(ticket_id, section="User Feedback", content="使用者確認: ...")`
**記錄**: `stm_append(ticket_id, section="Decisions Made", content="最終決策: ...")`

**進度更新**: `task_update(task_id, description="Step 4: Discuss — 等待使用者確認")`

**暫停條件**: 必須等使用者確認後才能進入 Step 5

---

## Step 5: Execute（執行）
**目的**: 根據確認的方案執行實作

**前置條件**: Step 4 使用者已確認方案

**動作**:
1. 建立 Git branch：
   ```
   git_create_branch(repo, branch_name="feature/leo/{ticket_id}" 或 "bugfix/leo/{ticket_id}", ticket_id="{ticket_id}")
   ```
2. 根據確認的方案，逐步執行：
   - **資料庫操作**: `run_bash` 執行 SQL / TypeScript 腳本
   - **程式碼修改**: `edit_file` 修改相關檔案
   - **設定修改**: `edit_file` 修改 config
   - **腳本執行**: `run_bash` 執行 gRPC 呼叫、npx 腳本等
3. 每個操作後立即驗證：
   - 資料庫 INSERT/UPDATE 後 → 查詢確認記錄
   - 檔案修改後 → `read_file` 確認內容正確
   - SFTP 上傳後 → 確認檔案存在
   - 腳本執行後 → 檢查 exit code 和 output
4. 如果任何步驟失敗：
   - 立即記錄到 Failures
   - 分析原因
   - 嘗試修復或回報使用者

**記錄**:
- `stm_append(ticket_id, section="Code Changes", content="修改: {檔案路徑}\n變更: {摘要}\nBranch: {branch_name}")`
- 失敗時: `stm_append(ticket_id, section="Failures", content="Step 5 失敗: {操作} - {錯誤訊息}\nRoot cause: {分析}\n修復: {修復方式}")`

**進度更新**: `task_update(task_id, description="Step 5: Execute — 執行中...")`

**暫停條件**:
- 遇到無法自行解決的錯誤 → 暫停，呈報使用者
- 操作涉及不可逆動作（push to main/staging, 刪除資料）→ 暫停，確認後繼續

---

## Step 6: Review with User（使用者 Review）
**目的**: 讓使用者 review 變更內容，確認品質

**動作**:
1. 整理變更摘要：
   ```
   git_diff(repo, args="--stat") — 總覽
   git_diff(repo) — 詳細 diff
   ```
2. 執行測試（如果適用）：
   ```
   run_bash(command="npm test" 或相關測試指令)
   ```
3. 格式化 Review 報告呈現給使用者：
   ```
   ## Review: {ticket_id}
   ### 變更摘要
   - 修改了 N 個檔案
   - 新增了 N 行，刪除了 N 行

   ### 變更詳情
   {每個檔案的變更說明}

   ### 測試結果
   {測試通過/失敗}

   ### Branch
   {branch_name}

   ### Diff
   {git diff output}
   ```
4. **等待使用者 review 回應**
5. 如果使用者要求修改 → 回到 Step 5 修正
6. 如果使用者確認 → 繼續下一步

**記錄**:
- `stm_append(ticket_id, section="Test Results", content="測試結果: ...")`
- `stm_append(ticket_id, section="User Feedback", content="Review 回饋: ...")`

**進度更新**: `task_update(task_id, description="Step 6: Review — 等待使用者 Review")`

**暫停條件**: 必須等使用者確認後才能進入 Step 7

---

## Step 7: Complete（完成）
**目的**: 收尾工作 — commit、push、更新 ticket 狀態

**前置條件**: Step 6 使用者已 review 通過

**動作**:
1. Commit 變更：
   ```
   git_commit(repo, message="{簡要描述}", ticket_id="{ticket_id}", files=[...])
   ```
2. Push branch（使用者同意時）：
   ```
   git_push(repo)
   ```
3. 整理最終報告：
   ```
   ## Ticket: {ticket_id} - {title}
   ### 變更摘要
   {修改了什麼、為什麼}
   ### Branch
   {branch_name}
   ### 需要確認的事項
   {是否需要 merge、deploy 等後續動作}
   ### Diff 摘要
   {關鍵變更}
   ```
4. 呈報使用者最終結果

**記錄**:
- `stm_append(ticket_id, section="Code Changes", content="Commit: [{ticket_id}] {message}\nBranch: {branch_name}\nPush: {yes/no}")`
- `stm_append(ticket_id, section="Decisions Made", content="完成方式: {摘要}")`

**進度更新**: `task_update(task_id, status="completed", description="Step 7: Complete — 已完成")`

**暫停條件**: 無，繼續 Step 8

---

## Step 8: Retrospective（回顧反思）
**目的**: 反思這次 work loop 的表現

詳細協議見: `skills/work-loop/RETROSPECTIVE.md`

**動作**:
1. `spawn_agent(agent_type="analyze", task="回顧 {ticket_id} 的 work loop，執行 Retrospective Protocol")` — 獨立反思：
   - 讀取 `stm_read(ticket_id)` 取得完整工作紀錄
   - 比較初始分析（Step 2）vs 最終結果（Step 7）
   - 哪些方法被嘗試又放棄了？（從 Approaches Considered 提取）
   - 從 Failures 中學到什麼？（用 `stm_get_failures(ticket_id)` 取得）
   - 自我評估信心度（1-5），依 RETROSPECTIVE.md 的量表
2. 記錄反思結果

**記錄**: `stm_append(ticket_id, section="Retrospective", content="初始假設 vs 結果: ...\n嘗試後放棄的方法: ...\n信心度: N/5")`
**記錄**: `stm_append(ticket_id, section="Lessons Learned", content="技術面: ...\n流程面: ...\n工具面: ...")`

**暫停條件**: 無，繼續下一步

---

## Step 9: Memory Update（記憶更新）
**目的**: 將經驗蒸餾到長期記憶

**動作**:
1. `stm_distill(ticket_id)` — 蒸餾本次 ticket 的經驗到 knowledge 檔案
   - 提取可重用的 pattern
   - 提取重要的 gotcha / trap
   - 提取新學到的業務規則
2. 每完成 5 個 ticket：`cross_ticket_review()` — 跨 ticket 模式分析
   - 檢查是否有重複出現的問題模式
   - 識別系統性的改進機會
   - 更新 knowledge 檔案中的 pattern
3. 檢查知識庫大小，必要時 `compress_knowledge()`
   - 合併重複的 pattern
   - 移除過時的資訊
   - 壓縮冗長的描述

**暫停條件**: 無，Work Loop 結束

---

## 失敗處理

任何步驟失敗時，遵循以下協議：

1. **立即記錄**: `stm_append(ticket_id, section="Failures", content="Step N 失敗: {原因}\n操作: {做了什麼}\n錯誤: {完整錯誤訊息}")`
2. **不要隱藏錯誤**: 記錄完整的失敗脈絡，包含 command output、error stack、當時的假設
3. **分析 root cause**: 是什麼導致失敗？是假設錯誤、工具錯誤、還是環境問題？
4. **嘗試修復**: 如果修復方式明確且風險低 → 修復後繼續
5. **回報使用者**: 如果修復不確定或風險高 → 暫停，呈報使用者決定

**常見失敗模式**:
- 資料庫操作失敗 → 檢查連線、SQL 語法、資料類型
- gRPC 呼叫失敗 → 檢查 service 是否運行、參數是否正確
- 檔案操作失敗 → 檢查路徑、權限
- Git 操作失敗 → 檢查 branch 狀態、conflict

---

## 進度追蹤

- 每進入一個 Step，用 `task_update(task_id, description="Step N: {名稱} — {狀態}")` 更新狀態
- 使用者隨時可以用 `task_list()` 查看進度
- 狀態值對照：
  - `pending` — 等待中（尚未開始）
  - `in_progress` — 進行中
  - `completed` — 已完成
  - `cancelled` — 已取消

---

## 快速參考：Tool 對照表

| 步驟 | 主要 Tools | 記錄 Section |
|------|-----------|-------------|
| Step 1: Retrieve | stm_search, memory_search, stm_read, stm_get_failures | Ticket Analysis |
| Step 2: Analyze | spawn_agent(explore), spawn_agent(analyze), jira_get_ticket | Ticket Analysis, Approaches Considered |
| Step 3: Debate | spawn_agent(debate_pro), spawn_agent(debate_con) | Approaches Considered |
| Step 4: Discuss | (呈現結果，等待使用者) | User Feedback, Decisions Made |
| Step 5: Execute | run_bash, edit_file, git_create_branch, read_file | Code Changes, Failures |
| Step 6: Review | git_diff, run_bash(test) | Test Results, User Feedback |
| Step 7: Complete | git_commit, git_push | Code Changes, Decisions Made |
| Step 8: Retrospective | spawn_agent(analyze), stm_read, stm_get_failures | Retrospective, Lessons Learned |
| Step 9: Memory Update | stm_distill, cross_ticket_review, compress_knowledge | (寫入 knowledge) |

---

*Last Updated: 2026-04-16*
