---
name: project-beta-program-api-access
description: How to list beta programs and add/remove participations over REST (lis-core-service /api prefix + HS256 JWT); creating a program itself has no API
metadata: 
  node_type: memory
  type: project
  originSessionId: d2c7498f-5248-41c2-8a77-bb8540f34754
  modified: 2026-08-03T23:37:07.396Z
---

Beta programs are the org's practice-level feature-flag mechanism (`betaProgram` +
`beta_program_participations`, read by consumers via gRPC
`CustomerService.FetchCustomerBetaProgramsForClinic`).

**Base URL** (LIS-backend-coreSamples, the Nest one — *not* the Go v2 service):
- prod: `https://api.vibrant-wellness.com/v1/lis/lis-core-service/api/...`
- staging: `https://api.vibrant-wellness.com/v1/lis/lis-corestaging-service/api/...`

The **`/api` segment is required** (`app.setGlobalPrefix("api")`). Omit it and the
ingress returns a confusing `404 {"message":"ENOENT: ... '/client/index.html'"}`.
Do not confuse this with `/v2/lis/coresamples/...`, which is the **Go** v2 service
and answers a plain-text `404 page not found` for these paths.

**Auth**: HS256 JWT signed with the same `JWT_SECRET_PROD` the EMR service uses for
upstream calls (claim set + algorithm per `TokenHelperService` in
lis-backend-emr-v2). Send it in `Authorization` with **no `Bearer` prefix**.
Missing token → `"no token present in request"`.

**Endpoints**
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/sync/get-beta-program-list` | all programs: id, name, description, isActive, allow_self_signup |
| POST | `/api/beta-program-participation` | body: `beta_program_id`, `customer_id`, `clinic_id` |
| DELETE | `/api/beta-program-participation` | same shape |
| POST | `/api/beta-program-participations/batch-add` | `{items: [{beta_program_id, customer_id, clinic_id}]}` |
| DELETE | `/api/beta-program-participations/batch-delete` | same shape |

**gRPC is the primary interface — and it is NOT named after beta programs.**
VP-16490 "Feature Access Management" on `lis.CustomerService` (prod v1
`192.168.60.6:30276`, verified working 2026-08-03) is the management API:

| RPC | Request | Notes |
| --- | --- | --- |
| `GetFeatureAccessWhitelist` | `beta_program_id`, `search_input` | lists every entry for a program, with customer_name / clinic_name / added_by / added_date |
| `AddFeatureAccessRecord` | `beta_program_id`, `customer_id`, `clinic_id`, `internal_user_id` | **`customer_id` set = provider-level, `clinic_id` set = practice-level; put 0 in the one that does not apply** |
| `RemoveFeatureAccessRecord` | `id` (participation record id), `internal_user_id` | |
| `SearchProvidersAndPractices` | `search_input`, `limit` | admin picker |

**This is why I could not find it:** I searched `beta`, `program`, `participation`,
`enroll` — the RPCs say **FeatureAccess**. And my first pass searched only
lis-backend-emr-v2's `src/proto/customer.proto`, which is a **subset copy** with
none of these RPCs. Use the authoritative proto
(`LIS-backend-coreSamples/protos/customer.proto`); load it with emr-v2's
node_modules if coreSamples has no deps installed.

**Two gotchas that cost real time:**
1. **Participation takes a numeric `beta_program_id`, never the name**, and
   `addBetaProgramParticipation` calls `betaProgram.findUniqueOrThrow` — the program
   row must already exist.
2. **There is no create-program API.** Zero `prisma.betaProgram.create` anywhere in
   the codebase; every path is `findMany`/`findUnique`/`findUniqueOrThrow`. A new
   program still needs a DB insert. So "enrolling practices" is self-service but
   "introducing a new flag" is not.

**Do not infer existence from `FetchCustomerBetaProgramsForClinic`** — it only
returns the programs a given clinic participates in, so it cannot distinguish
"program does not exist" from "program exists with zero participations". Use the
list endpoint. (I made exactly this mistake on VP-17584; see
[[feedback_never_conclude_breakage_from_a_quiet_window]] for the same shape.)

Known ids worth remembering: `express_checkout`=2 (the PRD's express-checkout
toggle is itself a beta program, so rollout ordering can be derived from
participation data), `gz_ny`=33 (VP-17117's NY routing gate). 39 programs total as
of 2026-08-03.
