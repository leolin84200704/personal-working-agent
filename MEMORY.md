# MEMORY - Knowledge Index

> Agent 的累積知識索引。每個記憶都是從實際操作中學習而來。

---

## Index

- [Repos](#repos) - 各 repo 的功能與架構理解
- [Patterns](#patterns) - 常見修改模式與做法
- [Gotchas](#gotchas) - 容易踩的坑與注意事項
- [Questions](#questions) - 曾問過的問題與答案
- [Jira](#jira) - Jira 相關知識

---

## Repos

### LIS-transformer
- **用途**: HL7 轉換服務，將 LIS 格式轉為 HL7
- **主要技術**: Python, Django
- **關鍵檔案**:
  - `src/hl7_parser.py` - HL7 解析器
- **注意**: ...

### LIS-transformer-v2
- **用途**: HL7 轉換新版
- **狀態**: 🟝 待探索

### EMR-Backend
- **用途**: EMR 系統後端
- **主要技術**: Java, Spring Boot
- **狀態**: 🟝 待探索

---

## Patterns

### 新增檢驗項目對應
1. 修改對應的 mapping 檔案
2. 更新測試資料
3. 需要 restart service

### HL7 Parser 修改
- 總是需要加上單元測試
- 特殊字元處理要注意 escape sequence

---

## Gotchas

### 常見錯誤
- 🟝 待填寫（從實際操作中學習）

---

## Questions

### Q: 如何判斷要修改哪個 repo？
> **A**: 先看 ticket 標題關鍵字，再搜尋各 repo 的相關檔案

---

## Jira

### Project Keys
- LIS - LIS 相關專案
- EMR - EMR 相關專案

### Custom Fields
- `customfield_10000` - Sprint

---

*This file grows with every interaction. Last Updated: 2026-04-06*
