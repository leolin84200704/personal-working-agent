---
name: getLegacyBundleMapping API clinic-level bundle format
description: VP-15302 — API response clinicId field format and Bundle.java deserialization notes
type: project
originSessionId: e347efec-ad1a-4826-bc5f-1da577b2d0bd
---
`getLegacyBundleMapping` API response includes a `clinicId` field (camelCase):
- `null` → customer-level bundle
- integer → clinic-level bundle

`Bundle.java` uses Gson auto-deserialization for the `clinicId` field — no `@SerializedName` annotation needed since the field name matches the JSON key.

**Why:** Knowing this avoids unnecessary annotation additions or incorrect field naming when working with bundle data.

**How to apply:** When reading or modifying Bundle-related code, remember clinicId is nullable and distinguishes customer-level vs clinic-level bundles.
