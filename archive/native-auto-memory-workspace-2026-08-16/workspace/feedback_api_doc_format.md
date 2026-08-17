---
name: API doc format preference
description: Leo wants API docs in team-standard structured markdown (Overview/Architecture/Database/Endpoints with curl), not raw OpenAPI YAML
type: feedback
originSessionId: 02a26321-ab4a-4c25-8b9b-e103083f0274
---
API docs should follow the team's structured markdown format, not raw OpenAPI/Swagger YAML specs.

**Why:** Leo explicitly rejected the raw OpenAPI YAML format and asked for docs matching the style used in `docs/agent-enrollment-pipeline.md` — with Overview, Architecture diagram, Key Behaviors table, Database schema, and Endpoints with curl examples + JSON responses.

**How to apply:** When writing API documentation for any new endpoint, use the team format (Overview → Ticket → URL → Architecture → Key Behaviors → Database → Endpoints → Status Flow → Frontend Notes). See `docs/vendor-inquiry-swagger.md` and `docs/agent-enrollment-pipeline.md` as references.
