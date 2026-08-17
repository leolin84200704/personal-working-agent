---
name: project_vp16945_reminder_provider_tz
description: "VP-16945 reminder email provider-timezone — design decided (A), deferred until VP-16943 ready"
metadata: 
  node_type: memory
  type: project
  originSessionId: 74e762f1-3b9d-40c0-b5f2-49d440a3ee58
---

VP-16945 [BE] Clinical Consult - Send Reminder Emails Based on Provider Timezone（epic VP-16942，assignee Leo，Dev To Do）。2026-06-09 與 Leo 討論定案，**deferred 未動 code/DB**，等依賴 VP-16943 進度到位再做。

**問題本質**：reminder.service.ts:229 已 per-recipient 讀 `v2_calendar.timezone` + PST fallback，但缺 UTC 守衛。prod ~18k provider/clinicadmin 的 `v2_calendar.timezone='UTC'`（VP-16202 legacy backfill 填不出值留 UTC）→ 這批 reminder render 成 UTC，這就是 PM 寫「currently display times in UTC」的真因。核心矛盾：字串 `'UTC'` 同時代表「未設」與「真 UTC」，加 `!== 'UTC'` 守衛會犧牲真 UTC（永遠改不了）。

**design A 已作廢（2026-06-19 更正）**：原本以為 provider TZ 會寫回 `v2_calendar.timezone`，**錯**。VP-16943（Fan，已 Dev Complete 6/11）做成獨立 setting：**setting_name=`'timezone'`，customer+clinic scope（per-provider），預設 `'PST'`**，經 core `getSettingByCustomerClinic` 讀 / `EditCustomerClinicSettings` 寫（`src/setting/setting.service.ts` getTimezoneSetting/setTimezoneSettingCustomer；REST `/setting/getTimezoneSetting`、`/setting/setTimezoneSettingCustomer`）。**存值不正規化**（原樣存，FE 傳縮寫 "PST"/"EST" 或 IANA 都可能）。
→ **不需要** v2_calendar legacy-UTC migration（整個砍掉）。

**正確修法（design A'）**：reminder.service 對 **provider 收件人**改讀 `'timezone'` setting（default PST），值做 abbrev/IANA→IANA 轉換後給 date-fns，DST-correct 顯示 PST/PDT。

**開工前必確認**：(1) FE（VP-16944，仍 Dev In Progress）存縮寫還 IANA → 決定要不要做 PST→America/Los_Angeles mapping（"PST" 非合法 IANA）；(2) 範圍：只改 provider 那封 vs 全 recipient（reminder per-recipient 是 VP-16664 刻意）。

依賴：VP-16943 **DONE**；VP-16944 [FE] Capture provider TZ on login（Dev In Progress，不擋 BE，default PST 先頂）。

**已實作（2026-06-19，PR #499 → stage_test，branch feature/leo/VP-16945）**：
- setting 存在 `lis_core_v7.setting`（value）+ `customersettingonclinics`（customer+clinic→setting_id）；**prod 現況 6793 個 provider 全部 = `"PST"`（縮寫,非 IANA）→ 所以 abbrev→IANA mapping 是必須**。
- `timezone.util.resolveIanaTimezone()`（abbrev→IANA / IANA passthrough / default America/Los_Angeles）。
- `reminder.service` 每個 recipient **每次發信即時 call gRPC `GetSettingByCustomerClinic`**(v1 SETTING_PACKAGE=CORE_RPC_STAGE,OAuth2 metadata via settingTool)取 `'timezone'`→normalize→date-fns DST。**完全不讀 `v2_calendar.timezone`**(Leo 指示)。
- 22 unit test 過、build/start:dev 過。
- 注意:meeting-request/public-booking 的**確認信**也有同樣「讀 v2_calendar 快取 email/tz」pattern（VP-17103 領域），本 PR 未碰,另案。
- 踩雷:`git add -A` 把 repo 裡未追蹤的一次性 scripts 也 commit → GitHub secret push protection 擋；改成只 add 我的檔。完整 STM `storage/short_term_memory/VP-16945.md`。
