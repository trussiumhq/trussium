# ADR-0031: Complete the deterministic routing milestone

## Status

Accepted

## Decision

Mark Milestone 7 complete after delivering deterministic provider/model routing, bounded retries and timeouts, fallback, circuit breaking, health filtering, decision telemetry, idempotency, and retry budgets. Keep adaptive weighting, distributed state, durable idempotency, and AI-assisted routing deferred.

## Consequences

The runtime has a complete bounded resilience foundation with explicit operational contracts. Future routing sophistication can be added as separate milestones without destabilizing the current deterministic behavior.
