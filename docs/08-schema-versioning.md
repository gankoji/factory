# Schema Versioning Strategy

## Scope

This document defines compatibility expectations for canonical data contracts in `/schemas`.

## Policy

1. Every domain payload includes `schema_version`.
2. Minor-compatible changes (new optional fields) retain the same major version.
3. Breaking changes (renamed required fields, enum value removals) require a new major version.
4. Readers must support the current major and previous major for one release window.

## Migration Example

### Example: `ticket` schema `v1 -> v2`

Change:
- Add new optional field `risk_class: "low" | "medium" | "high"`.

Implementation:
1. Update pydantic model with optional field.
2. Regenerate `/schemas/ticket.schema.json`.
3. Add DB migration if column persistence is required.
4. Keep readers defaulting missing `risk_class` to `medium`.

Compatibility:
- `v1` payloads continue to validate through defaults.
- `v2` writers can emit field immediately after rollout.
