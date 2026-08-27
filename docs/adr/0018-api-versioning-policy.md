# ADR 0018 — Explicit HTTP API versioning

- Status: Accepted
- Date: 2026-08-27

## Decision

Version the public HTTP API by a major path prefix, currently `/v1`. Preserve
backward compatibility within a major version for existing request fields,
response fields, status semantics, and streaming events. Breaking changes
require a separately reviewed major path and migration documentation.

## Consequences

Clients have a stable integration target independent of package, image, chart,
SDK, provider, and capability release versions. The runtime does not negotiate
or silently redirect API versions; future majors can coexist during migration.
