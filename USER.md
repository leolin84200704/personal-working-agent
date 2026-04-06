# USER - Leo's Preferences

> 此檔案記錄 Leo 的工作偏好、習慣與期望，讓 Agent 能更符合他的使用方式。

---

## 工作習慣

### 分支命名
- **必須**使用前綴: `feature/leo/` 或 `bugfix/leo/`
- Ticket ID 後面可以加簡短描述，例如: `bugfix/leo/LIS-123/fix-hl7-parser`

### Commit Message 風格
- 喜歡**簡潔**但**清楚 why** 的 message
- 格式: `[LIS-123] 修復 HL7 parser 在特殊字元的處理`
- 不需要過於詳細的 body，除非是複雜的 refactoring

### PR 標題
- 格式: `[{ticket_id}] {簡短標題}`
- 例如: `[LIS-456] 新增 CBC 檢驗項目對應`

### Code 風格偏好
- Python: 遵循 PEP 8，使用 type hints
- Java: 遵循現有專案的風格
- TypeScript: 使用 ES modules，避免 any

---

## 溝通偏好

### 報告格式
完成 ticket 處理後，提供：
```markdown
## Ticket: LIS-123 - {標題}

### 修改摘要
- 修改檔案: src/hl7_parser.py (新增錯誤處理)
- 影響範圍: HL7 OBR segment 解析

### 分支
bugfix/leo/LIS-123

### 待檢查項目
- [ ] 測試資料是否完整
- [ ] 需要更新 API 文檔嗎？

### Diff 摘要
+ 新增 try-except 處理特殊字元
+ 修正 regex pattern
```

### 何時該問我
- 不確定哪個 repo 需要修改
- Ticket 描述模糊或矛盾
- 涉及資料庫 schema 變更
- 需要修改多個 repo 且有依賴關係
- 現有代碼看起來有問題但不確定要不要動

### 何時可以自己決定
- 明顯的 bug 修復
- 簡單的功能新增
- 測試程式的更新
- 文檔修正

---

## 重要禁忌

### 不要做的事
- ❌ 不要重複問我已經回答過的問題（記在 MEMORY.md）
- ❌ 不要在 message 中加 emoji
- ❌ 不要自己 merge 任何東西
- ❌ 不要修改 production config
- ❌ 不要在沒有測試的情況下改核心邏輯

---

## 工作流程偏好

1. **Scan tickets** → 產生待辦清單
2. **逐一處理** → 不要同時處理多個
3. **每完成一個** → 產生報告，等我檢查
4. **我檢查通過** → 繼續下一個
5. **我有問題** → 先修正再繼續

---

## 迭代方式

當你學到新東西時：
1. 更新對應的 memory 檔案
2. 在報告末尾簡單說明學到了什麼
3. 我會定期 review MEMORY.md 的內容

---

*Last Updated: 2026-04-06*
