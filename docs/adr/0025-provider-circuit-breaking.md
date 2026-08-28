# ADR-0025: Bound provider circuit breaking

## Status

Accepted

## Decision

Provider fallback tracks transient failures per provider. After a bounded threshold the provider is temporarily excluded; a cooldown permits a recovery attempt, and success closes the circuit.

## Consequences

Repeated upstream failures stop consuming request time while preserving deterministic routing. Circuit state is process-local and intentionally separate from health reporting and distributed coordination.
