# ADR-0033: Propagate tenant identity through runtime context

## Status

Accepted

## Context

Runtime API-key authentication now provides an optional boundary, but downstream logs, traces, and capability execution need a consistent tenant attribution field before authorization and usage controls can be layered on.

## Decision

Extend the frozen `ExecutionContext` with an optional `tenant_id`. The request-correlation middleware reads `X-Tenant-ID`, accepts only bounded identifiers containing alphanumeric characters and `-_.:`, and preserves the existing request context APIs through optional keyword arguments. Structured logging and HTTP tracing automatically inherit the field. Invalid values are ignored and never echoed in responses.

## Consequences

- Tenant attribution survives async and streaming execution without mutable request globals.
- Existing clients remain compatible when the header is absent.
- The value is attribution metadata, not authorization or isolation; later governance work must bind it to authenticated identity.
