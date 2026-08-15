---
date: 2026-08-14
slug: vp17714-clinician-switch-zoom-room
related:
- VP-17714
- VP-16520
- VP-16521
- VP-16410
- VP-16881
- VP-17065
distilled: true
---

# VP-17714 — 轉手 Clinical Consult 沒換 Zoom 房間

## 起點

Leo 只丟了一條 ticket 連結，沒有其他指示。ticket 標題掛 `[FE]`，P2，reporter 是 PM Yuchen，assignee 是 Leo。內容是一位 Clinical Educator 的轉述：provider 把 consult 從 Dr. Jessy Dhanjal 轉給她，她從 VI 行事曆點 Zoom 連結卻進到 Jessy 的個人會議室，provider 也在同一個連結裡等，她只好寄自己的連結過去，對方沒立刻看到信 → consult 遲到開始。最後一句是關鍵線索：「phone consultations do not appear to be impacted」。

## 探索路徑

STM `_index.md` 一眼就命中 VP-16520（換 clinician 的 cancel-and-rebook 編排）。讀它的 Lessons 第 1 條寫著新 event 會「抄 creator_calendar_id/practice_event_type/event_type/color/notes/location/**external_url**/timezone/accession_ids」—— `external_url` 就在複製清單裡。`docs/reference/trans-v2-calendar.md` §12 又寫「zoom links likely stored as external_url/manual」。兩條合起來假設就成形了，但那個 "likely" 是推測，必須驗。

`event.service.ts:4943` 確認 `external_url: original.external_url`。接著去 prod calendar DB 驗：

1. 先確認 `external_url` 到底裝什麼 → 按 clinician group by，每個人都有一個重複 55–81 次的 `/j/` 號碼（Suzette 5613862727、Dana 5114365088、Jessy 2639232847…）。**同一個值在單一擁有者身上重複幾十次 = 這欄綁的是人，不是事件。**
2. 怎麼找出歷史上所有的「換人」？一開始想用 event pair（同 accession、一取消一新建）去 join，撈到 4 組。但那是推論。真正的鐵證是 `accessionClaim.releaseForEvent` 寫進 `v2_event_accession_audit_log` 的 `reason = 'clinician switch reschedule, original event N'` —— 這是 `rescheduleClinicalConsult` 專屬的字串，查下去也是 4 筆，**同時證明了 FE 確實在打這個 mutation，不是還停在舊的 updateEventByPatient**。
3. 4 筆裡 3 筆是 Zoom、全部照抄舊房間；1 筆是 phone、照抄了 `808-333-6747`——那是**病人的**電話，照抄是對的。

到這裡 reporter 那句「phone 不受影響」就不再是巧合，而是根因的直接推論：**同一個欄位的擁有者隨介質而異**。這是整張 ticket 最有價值的一句話，而它藏在使用者的側面描述裡。

## 排除掉的東西

- **「錯連結會外溢到 Google/Outlook 行事曆」**——查了 practice 150105 只有 8 筆 zoom integration，google/outlook 各 0，歷來 `google_event_id`/`outlook_event_id` 全表為 0。反對「FE 兩段式修法」的這條理由不成立，我在回報時主動撤回。
- **`zoom_event_id` 相關的程式碼**——全表 0，`fireRescheduleSideEffects` 裡 `event.zoom_event_id &&` 那段在 150105 是死碼。
- **heuristic 會誤傷**——150105 的 `external_url` 只有 4 種形狀（空白 5870 / zoom.us 995 / 純電話 333 / other-text 6），沒有 teams、meet.google 或其他 URL，`includes('zoom.us')` 安全。
- **反向稽核撈到的第二筆 9577**——Emaline Brown 的連結房號 `81595562495` 是 **11 碼**（一次性排程會議），不是 10 碼 PMI，也不在任何 switch pair 裡 → 正常單場會議，不動。這個 10/11 碼的判別法是臨場從資料看出來的。

## 決策過程

Step 4 我提了 A（BE 解析新 clinician 的 PMI）/ B（FE 帶連結）/ A+B / C（不抄留空）四案，建議 A+B。

Leo 的回問把問題問到點上：**「我們在 reschedule 的時候可以讓前段直接放新的 url 嗎？如果是這樣的話還要改嗎？」**

這逼我去查 input model —— `RescheduleClinicalConsultInput` 沒有 `external_url` 欄位，所以「同一次 mutation 裡帶」現在辦不到。但我也誠實回報：FE **不改 BE 也做得到**，因為 `linkZoomMeetingUrlToEvent(eventId, meetingUrl)` 這個既有 mutation 就能覆寫，reschedule 又回傳含 `event_id` 的完整 Event。反對兩段式的理由只剩兩條真的成立：非原子（第二段失敗就退回今天的壞狀態，且無痕跡），以及 `generateZoomLinkForProvider` 每呼叫一次就 `POST /users/me/meetings` 開一場垃圾會議。

Leo 選 A + optional external_url。

第二個回合他問「改好之後需要別人配合嗎？還是能完全解決 bug？」——我列了 3 項配合（Mary 沒綁 Zoom / 3 筆歷史資料 / PM 改分類）+ 1 條殘留路徑（`updateEvent` → `replaceEventParticipants` 也能原地換人而不碰 external_url，且**沒有 audit 指紋可追**）。我試著反查歷史有沒有人走過那條路，發現訊號不可用：`replaceEventParticipants` 是 deleteMany+createMany，每次帶 participants 的 update 都會重寫 `created_at`，所以 `participant.created_at > event.create_time` 撈出來一堆雜訊（抽樣 30 筆，多數 external_url 與該 clinician 自己的 PMI 相符 = 根本不是換人）。

Leo 兩句話收掉：**「mary 不用管他，只要換人就走 reschedule，不管有沒有改時間」**——第二句直接把涵蓋率問題變成非問題，(ii) 不用做。

## 實作上的判斷

- 新 `getPersonalMeetingUrl` 而不是複用 `generateLinkForProvider`：後者會建會議，不能放在每次 reschedule 都會走的路徑上。
- **解析放在 `$transaction` 之前**——交易期間不能卡一個 outbound HTTP call。
- 解不出來時**清空 + logWarn**，不保留舊連結。理由：保留舊值等於保證把人導向錯誤的房間；清空只是缺資訊。後者可補，前者會造成實際傷害。
- in-place 分支只在 caller 明確給值時才寫 `external_url`，其餘完全不碰（保持原行為）。
- 全套測試用 worktree 跑 baseline 對照才敢說「零新增失敗」——base 17 fail、branch 16 fail，逐 suite diff 唯一差異是 flaky 的 `auth.guard.spec.ts`。這個習慣值得保留：這個 repo 本來就有 6–7 個 pre-existing 失敗 suite，不做對照根本沒辦法判斷。

## 產出

- prod 資料修正：event 12528（8/21 未來場次）Lillie → Suzette 的房間，`UPDATE 1`，反向稽核 0 殘留。
- PR https://github.com/Vibrant-America/LIS-transformer-v2/pull/565（draft → stage_test），2 commits 切在 revert 邊界：能力 / 接線+測試。
- `docs/reference/trans-v2-calendar.md` 部分刷新（§4.1/§11/§12/§13），檔頭標明刷新範圍，只寫已部署行為。
- factory lesson PR https://github.com/leolin84200704/project-agent-factory/pull/27（owner-bound 欄位不可照抄；第二個 case 引 VP-16881 的 msh06）。
