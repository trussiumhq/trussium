# ADR-0023: Apply provider fallback to non-streaming chat

## Status

Accepted

## Decision

The chat API delegates non-streaming completion to the provider router when capability-compatible providers are registered. Streaming continues through the existing capability pipeline until resumable stream semantics are defined.

## Consequences

Transient provider failures can be recovered without changing the public response contract. Provider adapters remain unchanged, and deployments with one configured capability preserve their existing execution path.
