# ADR-0024: Deterministic chat model fallback

## Status

Accepted

## Decision

Non-streaming chat may try a bounded, explicitly ordered model list within each selected provider. Model fallback is nested inside provider fallback and only advances for transient failures.

## Consequences

Operators can recover from unavailable or overloaded models without changing the client contract. Streaming and unbounded model discovery remain outside this feature.
