# ADR 0015 — Consistent HTTP error envelopes

- Status: Accepted
- Date: 2026-08-27

## Decision

Normalize FastAPI request-validation failures to the existing Trussium JSON
error shape: a `detail` object containing a stable `code` and safe `message`,
with bounded field paths for validation failures. Runtime-owned errors retain
their existing codes and messages. Rejected values, raw framework messages,
credentials, and payloads are never echoed.

## Consequences

Clients can parse validation and runtime failures through one predictable
envelope while preserving existing status codes and error identifiers. The
envelope is limited to JSON responses; SSE error events retain their existing
normalized event contract.
