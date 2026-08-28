# ADR-0022: Deterministic provider fallback

## Status

Accepted

## Decision

Provider fallback follows the sealed registry’s explicit priority order and only advances after transient rate-limit, timeout, connection, or upstream failures. Non-transient failures and cancellation are immediately preserved.

## Consequences

Fallback is predictable and provider-neutral. Health-aware routing, circuit breaking, and model fallback can later refine candidate eligibility without changing the ordering contract.
