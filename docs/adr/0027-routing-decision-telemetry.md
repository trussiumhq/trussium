# ADR-0027: Emit bounded routing decision metadata

## Status

Accepted

## Decision

Provider routing emits one immutable decision per provider attempt and logs a bounded structured event. Consumers may receive decisions through an optional callback without changing execution return values.

## Consequences

Fallback behavior becomes observable and testable while preserving privacy boundaries. Aggregation, metrics, and distributed traces can consume the stable event later.
