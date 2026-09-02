# 2026-09-02 — VP-18080 taxonomy + VP-18066 envelope (PH-847/PH-844 arc)

Related: PH-847, PH-844, VP-18080, VP-18081, VP-18066, QH-6962, QH-6947,
VP-17691, VP-17760, LIS-7690

## Arc

Leo handed PH-847 bare (2026-08-31). Intake found it was a cross-service
taxonomy split: both quote (pricing, Go) and order (emr-v2) pass the
order-management eligibility-check's PascalCase codes through verbatim, while
order's own pre-eligibility layer speaks snake_case — same fact, different
layer, different code. Proposed snake canonical + mechanical converter at both
edges + failures[] as the uniform carrier (additive on rejected); Leo probed
the diff and my judgment over three turns, then approved posting the proposal
to PH-847 (comment 186020, posted with his 發布). PM (Xiaoye) accepted verbatim
next morning and cut VP-18080 (me, order half), VP-18081 (Rui, quote half —
clone; split inferred from committer rosters, never stated in the tickets),
and split my "optional scope extension" into PH-844/VP-18066.

## Decisions that held

- Mechanical converter over lookup table: validated twice — the real enum
  turned out larger than mintlify's list (15 vs 8, Confluence 2517139459 v9),
  and an undocumented reason (unsupported_test_codes) hit the fallback and
  still produced a coded failure.
- Leo's scope directives arrived mid-flight and cut cleanly: 只改自己的 repo
  (dropped transformer/pricing halves of VP-18066 — committer rosters decided
  ownership), then 跟著文件走 + no Rui handoff (killed the fixture-handoff
  draft; docs are the sync mechanism, not a side-channel).
- Debate critic earned its cost: caught the duplicate-branch patientId
  BLOCKER (transformer, later moot), the nonexistent response_json column in
  my persistence claim, and the Ginzap-reorder PHI trap (pricing, later moot).

## What bit

- Staging E2E fought test-data reality for 3 rounds: staging patients are
  flat (all clinic 3194), PatientNotInClinic is NOT enforced by staging
  order-management (clinic 99999 → eligible), and the winning move was
  probing the upstream read-only to SELECT a failing subject
  (IncompletePatientInfo patient 3148287) instead of guessing subjects and
  placing orders. 6 stray staging orders placed+cancelled along the way,
  cleanup 100% reverse-verified.
- unsupported_test_codes mystery: staging pricing runs ghost image 69ce1dd4 —
  a commit on NO branch — emitting the pre-rename `unknownCodes` key; prod
  (207657e) emits `unknown_codes` and already matched the docs. Fix landed as
  PR #399 (accept both keys). Family: spec-page≠deployed-service /
  stale-deploy lessons — verify the DEPENDENCY's deployed version before
  blaming your own layer.
- LIS-7690 lesson re-broken: `env | grep` in-pod printed the staging bearer
  ORDER_API_TOKEN_STAGING into the transcript. Select named fields, never
  grep whole env/configmaps. Candidate hook noted in STM retrospective.

## State at close

- emr-v2 prod (582c00d, promotion #400): VP-18080 fully live (prod smoke 7/7,
  incl. direct prod upstream probe proving PascalCase still flows in and
  snake flows out); VP-18066 emr-v2/FHIR half live (guard-layer envelope
  proven staging+prod; controller-layer proven by supertest only — RS256
  vendor token not self-mintable, stated openly).
- Open: Jira transitions (QA twins QH-6962/QH-6947 pending — asked Leo whether
  to move Dev In Progress → Done); mintlify/Confluence updates are
  api-product's (canonical snake table, unsupported_test_codes,
  unknownCodes→unknown_codes key doc); my own Confluence 2485977089 needs a
  manual PascalCase-list edit (MCP cannot update pages); VP-18066's not-ours
  rows await Leo's decision on the ownership-note draft; pricing-team note
  about the ghost staging image rides in PR #399's body.
