# ADR-0035: Propagate application identity through runtime context

## Status

Accepted

## Context

Tenant and project attribution are available in the runtime context. Governance also needs to distinguish client applications within a project without coupling request handling to a persistence layer.

## Decision

Extend the frozen `ExecutionContext` with optional `application_id`. The request-correlation middleware reads `X-Application-ID` and applies the same conservative bounded identifier rules as tenant and project identity. Existing context APIs remain compatible through optional keyword arguments. Structured logs and HTTP traces inherit the field automatically.

## Consequences

- Application attribution survives asynchronous and streaming execution.
- Existing clients remain compatible when the header is absent.
- Credential ownership, authorization, quotas, and durable application records remain follow-up controls.
