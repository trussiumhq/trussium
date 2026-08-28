# ADR-0029: Bound chat idempotency at the API edge

## Status

Accepted

## Decision

Cache only successful non-streaming chat results keyed by an explicit client idempotency key and canonical request fingerprint. Keep the cache process-local and bounded; reject conflicting key reuse and never cache failures or streams.

## Consequences

Client retries do not duplicate successful provider work within one process. Distributed replay protection and durable storage remain deployment concerns.
