# ADR 0017 — Consistent non-blank request validation

- Status: Accepted
- Date: 2026-08-27

## Decision

Use a shared stripped, non-empty string type for normalized capability request
models. Apply it to model identifiers and user text across capability
contracts, including list items. Reject whitespace-only values before provider
execution.

## Consequences

Clients receive deterministic local validation and providers never receive
accidental blank identifiers or text. Existing valid values are preserved after
trimming; provider error, response, streaming, and privacy contracts remain
unchanged.
