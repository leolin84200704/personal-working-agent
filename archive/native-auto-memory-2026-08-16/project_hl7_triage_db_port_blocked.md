---
name: project-hl7-triage-db-port-blocked
description: "Prod-DB/VPN reachability map (2026-07-06): internal 192.168.60.x gRPC ALWAYS needs Cisco VPN; Azure MySQL 3306 works without VPN on some networks; overnight VPN auto-disconnect killed the 4 AM triage runs; vpn CLI 'connect' tears down a live session"
metadata: 
  node_type: memory
  type: project
  originSessionId: 29343104-4191-4ed2-88ff-4093342a1d8b
  modified: 2026-08-16T01:42:31.235Z
---

Reachability map for prod dependencies from Leo's Mac (established 2026-07-06 by live testing, revising an earlier wrong "corp LAN blocks all non-443" theory):

- **Internal endpoints `192.168.60.x` (gRPC, incl. the repush `resultgeneration` service at 192.168.60.6:31317) are unreachable without the Cisco Secure Client VPN (utun, head-end 45.24.217.146).** Any repush/gRPC work requires the VPN up, period.
- **Azure MySQL `lisportalprod2...:3306` was reachable both with the VPN and without it (via en0 on the 10.7.4.x/10.7.5.x LAN)** on 2026-07-06 afternoon — yet timed out at 4 AM on 2026-07-05/06 while 443 worked. So DB reachability depends on the network path at run time (VPN state and/or which network the Mac is on overnight); don't assume a single fixed cause. `nc` to `1.1.1.1:3306` proves nothing — nothing listens there.
- The Cisco VPN **auto-disconnects overnight**, so the 4 AM launchd triage often runs without it.

**Cisco Secure Client CLI foot-guns** (`/opt/cisco/secureclient/bin/vpn`):
1. `vpn state` prints a transient `>> state: Unknown` first — parse the LAST state line only.
2. `vpn connect <host>` **tears down an existing session before reconnecting** — on 2026-07-06 a test misread the state and disconnected Leo's live VPN. Only call it when the last state is unambiguously `Disconnected`.
3. Headless reconnect outcome is inconsistent: on 2026-07-06 it failed ("Connect capability is unavailable" — SSO/GUI agent holds it). On 2026-07-07, from a cleanly `Disconnected` state, `vpn connect 45.24.217.146` succeeded headlessly (final `vpn state` showed `Connected`) and Azure MySQL 3306 became reachable again — no GUI/human click needed that time. So: still safe to try `vpn connect` when state is unambiguously `Disconnected` (per rule 2), but don't assume it will fail — check `vpn state` afterward and only fall back to "ask Leo to reconnect via GUI" if it's still not `Connected`.

**How to apply:**
1. `DailyJob/hl7_fail/run_triage.sh` now has a pre-flight (branch `feature/leo/bug-triage-skill`, PR #8): test 3306 reachability, safe best-effort reconnect, else write a BLOCKED triage report + notification and exit 1. Effective in the launchd job only after the PR merges into the main checkout.
2. Before any prod-DB or repush work (bug-triage skill Step 1): `SELECT 1` for the DB AND `nc -z -w5 192.168.60.6 31317` if repush is needed; report BLOCKED (empty result ≠ no failures) with "VPN down — reconnect via Secure Client GUI" when they fail.
3. `triage_runner_*.py` `run_query()` returns `[]` on both connection failure and genuine empty results — never trust a bare empty list.
4. **The pre-flight works; the consume side is the gap** (2026-08-15). `hl7_fail` AND `result_fail` both wrote BLOCKED reports two days running (08-14, 08-15) and nothing downstream noticed — dream ran clean both nights. **Read the first section of a daily-job report before trusting it**; a BLOCKED/SKIPPED file is a gap, not a clean day. Two silent days = escalate. Once VPN returns, **backfill by re-running** (`bash DailyJob/<job>/run_*.sh`) instead of waiting for the next tick — the 08-15 backfill was not empty (undelivered 23→26, new Cascades permanent failure). See `long-term-memory/patterns.md` 「排程 job 寫出 BLOCKED 報告」.
