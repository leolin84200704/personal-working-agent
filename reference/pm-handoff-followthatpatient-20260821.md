# PM 議題：FollowThatPatient（Next Health）用 provider 帳號下單，單一帳號跨多個 location

> 2026-08-21。這是**唯一**一家在 ORC-12 送 provider 帳號（customer_id）而不是 NPI 的 EMR vendor。
> 其餘 5 家（MDHQ / THM / OptiMantra / Practice Fusion / NICHOLS）近 180 天 1,172 筆訂單全部送 NPI。

## 現象

Next Health 是連鎖，每個 location 一個 Vibrant clinic_id：
`2930 Next Health`、`8003`、`36290 Next Health Studio City`、`22106`、`144510`。

FollowThatPatient 的訂單長這樣（原始 HL7）：

| 欄位 | 內容 | 我們有讀嗎 |
|---|---|---|
| `ORC-12.1` | **provider 帳號 customer_id**（例 `43262^Emanuel, MD^Anna`） | ✔ 用它決定下單者 |
| `MSH-6` | **Vibrant clinic_id**（例 36290） | ✘ |
| `ORC-17` | **Vibrant clinic_id**（同上） | ✘ |

他們**已經正確地告訴我們是哪個 location**（而且送兩次），但我們的比對只用 `ORC-12` 的帳號，
診所是從我們自己的整合設定推出來的。

## 後果：已經誤送

`sample 2597376`（2026-07-16）：HL7 的 MSH-6 與 ORC-17 都寫 **36290**（Studio City），
我們送出 **2930**（主店）。原因是 `customer 43262`（Anna Emanuel）一個帳號掛在 4 個 clinic，
比對不看診所，內部排序永遠取 2930。

近期 4 筆 FollowThatPatient 訂單裡：

| 日期 | ORC-12 帳號 | HL7 說的 location | 我們送出的 clinic | 結果 |
|---|---|---|---|---|
| 2026-07-11 | 6263 Darshan Shah | 8003 | 8003 | ✔（該帳號只掛一個 location） |
| 2026-07-16 | 43262 Anna Emanuel | **36290** | **2930** | ✘ **誤送** |
| 2026-08-01 | 43262 Anna Emanuel | 2930 | 2930 | ✔（碰巧一致） |

也就是說：只要下單者是「一個帳號掛多個 location」的醫師，location 就是擲骰子。
Anna Emanuel 掛 4 個 location，錯誤率 3/4。

## 要跟他們／practice 談什麼（二擇一，或並行）

1. **每個 location 給獨立的 provider 帳號**（他們自己的資料裡已有這種形狀：NPI 1366420523
   那位醫師就是 `26232@2930` / `26308@8003` / `25899@36290` 三個帳號，運作正常）。
   Anna Emanuel（43262）與 NPI 1750446159（`2797@2930` / `6263@8003` / `19472@36290` / `30528@22106`）
   目前是混合狀態。
2. **我們改讀 ORC-17 / MSH-6**（他們已經在送，這是我方的工程工作），並請他們書面確認該欄位永遠帶
   Vibrant clinic_id。

補充：其餘 5 家 vendor 沒有可用的 location 欄位（近 180 天只有 24% 的訂單帶著我們認得的 clinic_id），
那是另一條、範圍更大的議題，不在這張單裡。
