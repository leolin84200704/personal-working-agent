---
name: api-product-sandbox-test-client
description: Sandbox OAuth test client creds + RS256 token recipe live at ~/src/credential/api-product-sandbox-test-client.md; sandbox FHIR blocked by VP-17522
metadata: 
  node_type: memory
  type: project
  originSessionId: 74a86038-7535-40be-9695-7c312bed462a
  modified: 2026-07-28T20:52:00.732Z
---

API-product sandbox (api-sandbox.vibrant-america.com) test client credentials + token recipe are stored at `~/src/credential/api-product-sandbox-test-client.md` (client `api-product-test-client-3194`, scopes result/report; POST /v1/oauth2/token with `algorithm=RS256`).

**Why:** 2026-07-28 FHIR 503 triage burned an hour re-deriving how to get a sandbox RS256 token; client registry lives in staging Auth0 postgres (192.168.60.11:5432, secrets hashed — read via ephemeral `kubectl run --image=postgres:16` pod), secrets themselves are only distributed out-of-band.

**How to apply:** for any api-sandbox auth'd testing, read that credential file first. Screenshot-pasted client_ids get OCR-mangled (capital I vs lowercase l) — verify against the `Client` table (`clientId`, `secretLast4`). As of 2026-07-28 every client_credentials CUSTOMER token fails the FHIR session check with 403 ([[VP-17522]] — session rows store NULL customer/clinic).
