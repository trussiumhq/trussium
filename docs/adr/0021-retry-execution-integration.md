# ADR-0021: Apply bounded retries at the execution boundary

## Status

Accepted

## Decision

The capability execution pipeline owns retry attempts and per-attempt provider request deadlines for non-streaming calls. Streaming calls remain single-attempt because replaying a partially emitted stream would duplicate client-visible events.

## Consequences

Provider adapters remain protocol-neutral and do not implement retry loops. Retry budgets and deadlines are centrally configurable; fallback, circuit breaking, and retry telemetry can build on this boundary later.
