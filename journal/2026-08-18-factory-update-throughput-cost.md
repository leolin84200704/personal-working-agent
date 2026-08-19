---
date: 2026-08-18
slug: factory-update-throughput-cost
related: [framework-sync, ENFORCEMENT-LADDER.md, WORK-LOOP.md, native-auto-memory-retirement]
distilled: true
---

# 2026-08-18 — 08-15/16 factory 大改動之後，每個 turn 慢了三成：量到的成本，還量不到的收益

Leo 回報「update factory 之後 vibrant-agent 明顯變慢」。用 `~/.claude/projects/-Users-hung-l-src-vibrant-america-working-agent/`
的 124 份 transcript 切三段比對（BEFORE 07-20~08-05、MID 08-06~08-14、AFTER 08-15~08-18，
factory 大改動落在 08-15/16）。**這份是問題的登記，不是結案** —— Leo 指示先記起來、過段時間再監測。

## 結論：不是模型也不是網路，是步驟數

單次 API call 的延遲沒有變壞，反而略好（opus-5 3.8s/call vs 先前 fable-5 4.9s）；
每次 call 的 context 中位數 198k → 166k，沒有膨脹。所以慢的來源只有一個：同一件事跑更多步。

實質 turn（工具數 ≥3）：

| 指標 | BEFORE | MID | AFTER |
|---|---|---|---|
| 工具呼叫/turn 中位數 | 9 | 10 | 13（+44%） |
| Bash/turn 平均 | 11.6 | 12.1 | 17.3（+50%） |
| turn 時間中位數 | 198s | 189s | 199s |
| turn 時間 p75 | 392s | 397s | 490s（+25%） |

只看 LIS 工作 session（排除 factory 自我維護）：工具/turn 8.6 → 11.7，分鐘/turn 2.56 → 3.48，皆 +36%。

## 成本花在哪（Bash 指令分類，佔全部 Bash 比例）

**先講一個容易誤判的地方**：把 LIS 工作 session 和 factory 自我維護 session 混在一起算，
會得到「讀 framework 文件從 1.1% 漲到 5.8%」的結論。拆開之後那是假象——framework 文件的閱讀
**全部集中在 factory session**（4.94 次/turn），LIS 工作是 0.16 → 0.15，完全沒變。
下面是只看 LIS 工作 session 的每個實質 turn Bash 呼叫數：

| 類別 | BEFORE (183 turns) | AFTER (27 turns) | 對應改動 |
|---|---|---|---|
| `git fetch/pull` | 0.44 | 0.93 | 原則 0 Sync With the World First（factory 9c9d4e8） |
| `git show/grep origin/main:` 讀檔 | 0.81 | 1.96 | 同上的副作用——不信任本機狀態，改從 remote ref 讀檔 |
| `git status/rev-list` | 0.30 | 0.56 | 同上 |
| memory 檔案 | 0.47 | 1.04 | session-start protocol + LTM 路由 |
| framework 文件 | 0.16 | 0.15 | 沒有變化 |
| 實際產品工作 | 8.87 | 12.96 | — |

最大一塊是「用 `git show origin/main:檔案` 當讀檔預設方式」。fetch 完並確認 working tree 沒有
diverge 之後，本機檔案就等於 origin/main，繼續走 git plumbing 是純儀式，而且更貴：不能用 Read
工具、沒有行號、每個檔案要重跑一次。同期 Read 工具用量從 1.11 掉到 0.71/turn，就是搬過去的量。

同期整體（含 factory session）的 Bash 中，做實際產品工作的比例從 70.8% 掉到 51.4%。

Guard 摩擦：被 hook 擋下的 tool_result 從 9.9‰ 升到 55‰（5.5 倍）。新增的
`protect-verification-assets`（19 次命中）、`validate-repo-language`（31）、repo-aware push guard（28），
加上常駐的 `remind-engineering-lessons`。

**已知誤報**：`remind-engineering-lessons.sh` 的 `RISKY_RE` 對整串指令做 grep，
2026-08-18 這次分析中，一支純唯讀的 Python 統計腳本因為內容含有 `mysql|psql|SELECT` 這串 regex 字面值
被 exit 2 擋掉，heredoc 沒寫進去要整個重跑。成本是每 session 至少一次 round-trip。修法應該是
只在這些字出現在實際 SQL/CLI 參數位置才觸發，而非出現在腳本內容裡。**尚未修，等 Leo 決定。**

## 另一個成分：最近一半的 session 不是 LIS 工作

| 期間 | LIS session | factory/自我維護 session |
|---|---|---|
| 07-20~08-05 | 14 | 1（7%） |
| 08-06~08-14 | 12 | 2（14%） |
| 08-15~08-18 | 5 | 4（44%） |

而 factory session 是最貴的（16 工具/turn、5.5 分鐘/turn）。Leo 感受到的「變慢」有一塊
其實是 agent 這幾天在維護自己。

## 誠實的部分：收益量不出來

試過用「Leo 出手糾正」當品質 proxy：1.6%（8/509）→ 3.4%（3/88）。AFTER 只有 4 天、
5 個 LIS session、88 個 user turn，這個數字什麼都不能證明。也找不到乾淨的案例可以說
「就是因為先 fetch 才避免了某個錯」。**現況是成本已實現、收益仍是假設。**
這正是 ENFORCEMENT-LADDER 想處理的問題的反面：規則一次上六條、hook 一次上五個，
沒有先量 baseline，就無法回答「哪一條真的在接住事故」。

## 已執行的處置（Leo 指令 2026-08-18）

vibrant 全部改用 Fable 5：互動 `fable[1m]`，四支 headless job 預設 `fable`。
理由是延遲相同但單位成本低很多——AFTER 期間互動 session 有 84% 跑在 opus-5 上（BEFORE 只有 32%），
而 opus-5 對 fable-5 的 sec/call 沒有優勢（3.8 vs 4.3）。

## 未結案 / 下次監測要看的

1. 換 fable 之後，工具/turn 與 min/turn 有沒有回到 8.6 / 2.56 附近 —— 若沒有，證實瓶頸是儀式不是模型
2. `remind-engineering-lessons.sh` 誤報要不要修
3. Sync-first 收斂成「每個 repo 每 session fetch 一次 + 確認沒 diverge，之後照常讀本地檔」
   —— 這是目前最大的可回收項，約 2 次 Bash/turn
4. `git fetch --all --prune` 改成只 fetch 需要的 branch
5. 樣本累積到 15+ 個 LIS session 再跑 `scripts/agent-perf-metrics.py` 重測，屆時才有資格回答「值不值得」

## 監測基準（`scripts/agent-perf-metrics.py`，2026-08-18 跑的原始輸出）

下次重測請用同一支腳本、同樣的視窗定義，數字才可比。

```
2026-07-20..2026-08-05   turns= 215 (LIS 213)  tools/turn=  9.0  dur_med= 198s  dur_p75= 392s  out/turn= 22016
                         bash= 2484  git-sync=9.2%   framework=1.0%  memory-idx=3.7%  product-work=70.8%  guard_blocks= 2.4/1k  model=claude-fable-5 64%
2026-08-06..2026-08-14   turns= 124 (LIS 118)  tools/turn= 10.0  dur_med= 189s  dur_p75= 397s  out/turn= 20168
                         bash= 1503  git-sync=7.2%   framework=1.1%  memory-idx=2.7%  product-work=70.4%  guard_blocks= 4.4/1k  model=claude-opus-5 50%
2026-08-15..2026-08-31   turns=  59 (LIS  40)  tools/turn= 13.0  dur_med= 183s  dur_p75= 490s  out/turn= 23845
                         bash= 1005  git-sync=16.8%  framework=6.9%  memory-idx=7.8%  product-work=51.4%  guard_blocks=28.1/1k  model=claude-opus-5 85%
```

判讀方式：`tools/turn` 回到 9 附近且 `product-work` 回到 70% 附近 = 儀式成本收斂；
若只有 model 欄變成 fable 而其他不動，代表瓶頸確實在儀式與 guard，不在模型。
