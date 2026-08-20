---
name: lis-prod-change-gate
description: The mandatory safety checklist for any prod-impacting change in an LIS backend repo (code, schema, config, or a prod DB data fix). Use BEFORE and DURING any change that can reach production — editing a backend service, adding an env var, altering a schema, running a prod UPDATE/DELETE, or preparing a push/PR. Trigger on "改 emr-v2 / 改 prod", "加個 env / 設定", "跑個 SQL 修資料", "要 push 了", "可以部署嗎". Each gate exists because skipping it caused a real incident — walk them in order and do not skip ahead.
---

# LIS Prod Change Gate

Every gate below is a scar. The point is not ceremony — it's that each skipped step has already cost a production incident at least once. Walk them in order; treat a gate you can't satisfy as a stop sign, not a formality.

Some gates are now also enforced by git hooks in `lis-backend-emr-v2/.git/hooks/` (noted inline). The hooks are a backstop, not a substitute for thinking — they only catch the literal cases.

## Gate 0 — Branch first
Never work on `main`/`master`/`staging`. Branch: `feature/leo/{ticket_id}` or `bugfix/leo/{ticket_id}`. For parallel/stacked tickets prefer a git worktree over in-place checkout (separate `prisma generate` + `node_modules` per worktree).

## Gate 1 — 4-part analysis (state it before touching code)
This is an IRON rule (re-broken on VP-16832). Write these four, in order, before editing:
1. **目的** — what problem this change solves
2. **改前** — what the system does *today* (read the actual code/config, not memory)
3. **改後為何有效** — why the new behavior fixes the problem
4. **改什麼** — the concrete edits

If you can't write "改前" from real code, you don't understand the change yet — stop and investigate.

## Gate 2 — Scope confirmation
If the ticket scope is ambiguous, run `ticket-requirements-clarify` first and confirm with the human/PM before coding. Prefer the minimal change; widening scope after confirmation is cheap, unwinding an over-built change is not.

## Gate 3 — Schema migration BEFORE deploy
emr-v2 prod is **not** Prisma-managed. Adding a non-optional column in the schema without first applying the `ALTER` to the prod DB makes that model return 500 "Unknown column" on every read (VP-16832). Sequence is fixed: **apply the migration to prod DB first, then deploy the code that reads it** — never the reverse.

## Gate 4 — Config yaml coupling (dual update, same change)
Any new `process.env.X` must be added to **both** `lis-emr-v2-config.yaml` and `lis-emr-v2-config-prod.yaml` (under `data:`) in the same change — proactively, not when asked. (INCIDENT-20260601, re-broken 3×.) Enforced by the `pre-commit` hook, but state the yaml edits explicitly so the human sees them.
Related: setting a capability flag enables a downstream pipeline — confirm the pipeline's config exists too (e.g. `result_enabled=true` needs vendor + sftp_result_path), or you enable something that can't actually run (VP-16968).

## Gate 5 — English-only source
All source/comments/migrations are English-only (replies to the user stay zh-TW). Enforced by the `pre-commit` hook (greps CJK in `.ts/.js/.sql`).

## Gate 6 — Test before push, and verify on LIVE not mock
Two distinct checks, both required for prod-impacting changes:
- **Test before push**: run the unit tests and make sure they cover the new logic *branches*, not just compile. Compile pass ≠ behavior correct (INCIDENT-20260601: a SFTP verify patch was pushed on a green build alone).
- **Verify on live, not mock**: a passing mock unit test is not "verified in prod". Reproduce the actual prod behavior against the real DB / running service before claiming a result. (VP-16850: an "empty result bug" was actually `max_advance_days=28` config, not a code bug.) Also verify the **peer-observed** state, not just your own side's log (INCIDENT-20260601: a lifecycle patch was verified only on the hanging pod, not the peer's session count → leaked for 3 days).
- `pre-push` hook runs `prisma generate` + `nest build`; a build failure is real, not a "stale/pre-existing" illusion (VP-16521 was a missing `prisma generate` after a branch switch).

## Gate 7 — Prod data fixes: bound the scope, then verify at every layer
For any prod `UPDATE`/`DELETE`:
- Bound the `WHERE` to the current session — time window **and** explicit IDs. Never widen "just to be safe" (cleanup filter scope rule).
- Remember SQL `NULL = NULL` is false — a JOIN/`WHERE` can silently miss rows (INCIDENT-20260529, customer 508387). After the write, **reverse-audit**: `SELECT` with a *broader* criterion to catch rows your filter missed.
- After a batch `INSERT`/`UPDATE`, verify **100%** of affected rows, never spot-check (VP-16175 sat PENDING for 33 days).
- **Consumer-layer readback, in the same work unit as the write.** A DB `SELECT` over the same connection that wrote only proves the row changed — it does not prove the serving path sees it (wrong DB/replica, cache, service reading a different source). Before reporting the fix done, read the changed data back through the layer downstream actually consumes — the core RPC / service API, not the DB. The fix is not "done" until this passes; it is part of the change, not an optional follow-up (VP-17810: the RPC readback happened only because Leo asked for it afterward).
  - For `lis_core_v7` data: `lis.AddressService` / `PatientService` etc. via the **cloud mirror `10.224.0.199:30276`** (protos in `lis-backend-emr-v2/src/proto/`; reachable from local with VPN, or `kubectl exec` into the emr-v2 prod pod using its `dist/proto` + grpc-js). On-prem v1 `192.168.60.6:30276` is dead (ECONNREFUSED even pod-side, observed 2026-08-20) — do not burn time on it.
  - No RPC covers the table? Then the readback is a **second, independent** DB connection (the account/path the consuming service itself uses), and say so explicitly in the report.

## Gate 8 — Push / deploy semantics
- A feature/bugfix branch push does **not** auto-deploy. To deploy, open a **PR targeting `stage_test`** for approval — never `git push staging` directly, even if the branch is unprotected.
- `main` is untouchable. The agent does not merge — the human decides.

## Gate 9 — Incidents: preserve evidence before you restart
A hanging/broken pod: **dump logs + `kubectl describe` before any `rollout restart` / `pod delete`** — otherwise the root cause is GC'd forever (INCIDENT-20260528).

## Final report (zh-TW)
Use the standard format: Ticket / 變更摘要 / Branch / 需要確認的事項 / Diff 摘要. Then stop for human review before commit/push.
