# Draft comment for VP-18066 (ownership split) — NOT POSTED

Scope note before implementation: of the four offenders, only one lives in a repo I own.

| Endpoint | Repo | Owner | Status |
| --- | --- | --- | --- |
| report 403 (FHIR) | lis-backend-emr-v2 | me | done on feature/leo/VP-18066 — envelope + x-request-id on the FHIR surface, incl. new RATE_LIMITED (429) / SERVICE_UNAVAILABLE (503) codes |
| patients 400 | LIS-transformer | transformer team (Yuxuan) | needs their change: global ValidationPipe has no envelope, nothing stamps x-request-id, plus three hand-written response branches; happy to hand over the recon notes |
| quote 400 | LIS-backend-v2-pricing | pricing team (Rui) | needs their change: bind errors leak Go struct names; note the request-id middleware currently runs after auth, so auth rejections carry no X-Request-Id |
| invalid bearer -> Cloudflare HTML | gateway/Cloudflare | api-product/infra | not fixable in any of the three services |

Suggest splitting the three not-mine rows into tickets for the owning teams (same target shape as POST /orders).
