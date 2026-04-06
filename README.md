# LIS Code Agent

> LIS 相關專案的自動化維護 Agent，協助處理 Jira tickets。

## 結構

```
lis-code-agent/
├── SOUL.md           # Agent 核心哲學與行為準則
├── IDENTITY.md       # Agent 角色定位與能力範圍
├── USER.md           # Leo 的工作偏好與習慣
├── MEMORY.md         # 累積知識索引
├── src/              # 原始碼
│   ├── core/         # 核心邏輯
│   ├── integrations/ # Jira, Git, Claude API
│   ├── memory/       # Knowledge base 管理系統
│   └── utils/        # 工具函數
├── config/           # 配置檔案
└── output/           # 生成的報告與文檔
```

## 設置

1. 複製 `.env.example` 為 `.env` 並填入配置
2. 安裝依賴: `pip install -r requirements.txt`

## 使用

```bash
# 手動執行一次 scan
python -m src.main scan

# 更新 memory
python -m src.main update-memory
```

## 安全

Agent 的 Git 操作受到嚴格限制：
- ✅ 只能創建 `feature/leo/*` 或 `bugfix/leo/*` 分支
- ✅ 只能推送到自己的分支
- ❌ 不能 force push 或 merge

## License

Internal use only.
