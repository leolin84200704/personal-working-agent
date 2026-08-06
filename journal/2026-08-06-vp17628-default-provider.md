# 2026-08-06 — VP-17628: orderingProviderId optional, clinic default provider fallback

Related: VP-17628, VP-17472, VP-17499, VP-17450, VP-17283, VP-17290

## What happened

Full work loop, one session: intake → explore → debate → design ruling (Leo + PM Chris Wu) → implement → live-verify → PR #328 (draft, staging) https://github.com/Vibrant-America/lis-backend-emr-v2/pull/328.

## Design evolution (three rounds — worth remembering the shape of this)

1. My Step-4 proposal: omitted provider → clinic defaultProvider → fallback token customer (portal parity). Leo initially approved the token-customer fallback.
2. Chris Wu (PM) superseded: unset default → ERROR, no token fallback; explicit provider always overwrites; credential-generation UI will force setting the default (Junjie).
3. Leo then objected to my flattened "one chain for all tokens" summary: a CUSTOMER-scoped token should order as the request's own customer, not consult the clinic default at all. Final matrix keyed by TOKEN TYPE, not one chain: customer token → self; clinic-only token → default-or-error; scope-less → must supply provider. Chris's rules apply to the clinic-token row only.

Lesson: when two stakeholders rule on "the fallback", check whether they are ruling about the SAME actor class. The reconciliation (matrix by token type) dissolved an apparent conflict.

## Ground-truth digging that paid off

- "Default provider" setting located by cross-repo trace: portal DoctorList.vue → `set_default_customer_id` → transformer-v2 setting.service.ts:3321 → clinic_setting {setting_name:'defaultProvider'} → owned by coresamples v2, RPC GetClinicSetting. emr-v2 already had setting.proto vendored (advocate found this — killed the "new dependency" objection).
- ClickHouse replica quantified the unset case: 52,615 active clinics = 37% usable / 37% EMPTY-STRING row / 26% no row. The empty-string form is as common as the usable form — a "row exists" check would have been wrong for 19k clinics. Live RPC probe confirmed: clinic 153884 returns a row with value='' active=true.
- Partner token shape verified by actually exchanging a sandbox client-credentials token: carries BOTH customer_id and clinic_id (OAuth embeds the client's bound ProviderID/PracticeID). So "pure clinic token" doesn't exist today; that path is forward-looking for clinic-bound credentials.

## Debate value

Advocate found setting.proto vendored + same-server (design got cheaper). Skeptic found: stale-base premise (VP-17499 resolveNamespaceCustomer second resolution point — verified real), money semantics (default provider's card gets charged — escalated to PM, accepted as portal parity), empty-value majority, RPC-failure-vs-unset conflation. Restricting the fallback matrix by token type killed the skeptic's namespace hole (S4) without extra code.

## Mechanics

- Worktree from origin/main (local main checkout was dirty on an old branch with staged residue of already-merged work — do not trust the working tree, verify origin).
- Pre-commit config-yaml-coupling hook caught GRPC_V2_SETTING_* — the lis-emr-v2-config(.prod).yaml snapshots are UNTRACKED files living in the MAIN checkout only; worktrees need them copied in for the hook to pass.
- Live verification pattern: called prod GetClinicSetting read-only with the repo's own proto before shipping the client — proto field naming (keepCase, isActive) and both configured/unset shapes confirmed against reality.
