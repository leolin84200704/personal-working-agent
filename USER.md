# Leo's Workflow Preferences

## 工作流程
1. Scan tickets → 產生 todo list
2. 一次處理一張 → 不要同時處理多張
3. 完成後 → 報告，等 review
4. Leo approve → 繼續下一張
5. 有問題 → 修完再繼續

## 什麼時候要問
- 不確定該改哪個 repo
- Ticket 描述模糊或矛盾
- 涉及 DB schema 變更
- 需要改多個有相依性的 repo
- 現有 code 看起來有問題但不確定要不要動

## 什麼時候可以自己決定
- 明顯的 bug fix
- 簡單的 feature addition
- Test / doc 更新

## 禁忌
- ❌ 自己 merge 任何東西
- ❌ 改 production config
- ❌ 改核心邏輯但沒有 test
