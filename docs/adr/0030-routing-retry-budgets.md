# ADR-0030: Bound retries across routing fallback

## Status

Accepted

## Decision

Provider routing receives a finite retry budget per call. Once transient failures consume the budget, routing stops and preserves the terminal failure; ordinary per-operation retry limits and circuit state remain separate controls.

## Consequences

Worst-case retry amplification is bounded across provider and model fallback. Budgets are process-local and configured centrally.
