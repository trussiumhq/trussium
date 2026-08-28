# ADR-0034: Propagate project identity through runtime context

## Status

Accepted

## Context

Tenant attribution is available in the runtime context. Governance requires a second bounded scope for teams and workloads within a tenant, without introducing mutable request state or coupling the runtime to a persistence system.

## Decision

Extend the frozen `ExecutionContext` with optional `project_id`. The request-correlation middleware reads `X-Project-ID`, applies the same conservative bounded identifier rules as tenant identity, and preserves existing context APIs with optional keyword arguments. Structured logs and HTTP tracing inherit the field automatically.

## Consequences

- Project attribution is available across asynchronous and streaming execution.
- Existing clients remain compatible when the header is absent.
- Authorization, tenant/project relationship validation, quotas, and durable project records remain separate follow-up controls.
