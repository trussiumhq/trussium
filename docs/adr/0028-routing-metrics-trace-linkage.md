# ADR-0028: Link routing decisions to metrics and traces

## Status

Accepted

## Decision

Emit routing decision counters with bounded labels and attach provider routing attributes to the active OpenTelemetry span. Instrumentation must not alter routing results or expose request data.

## Consequences

Operators can measure fallback outcomes and correlate them with request traces. High-cardinality model and payload labels remain intentionally excluded.
