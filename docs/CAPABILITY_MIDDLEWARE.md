# Capability Middleware Guide

Trussium provides ordered provider-neutral middleware around
`CapabilityExecutionPipeline`. Middleware can observe an immutable resolved
invocation, continue to the next layer exactly once, or intentionally return a
result or stream without invoking downstream work.

The contract is independent of HTTP, FastAPI, chat request models, providers,
and transports. Existing applications configure no middleware by default and
retain their prior execution behavior.

## Public contract

One middleware implements both execution modes:

```python
from collections.abc import AsyncIterator
from time import monotonic

from trussium.capabilities import (
    CapabilityExecuteNext,
    CapabilityInvocation,
    CapabilityStreamNext,
)


class TimingMiddleware:
    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        started_at = monotonic()
        try:
            return await call_next()
        finally:
            record_duration(invocation.capability_name, monotonic() - started_at)

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ) -> AsyncIterator[object]:
        async def events() -> AsyncIterator[object]:
            started_at = monotonic()
            try:
                async for event in call_next():
                    yield event
            finally:
                record_duration(invocation.capability_name, monotonic() - started_at)

        return events()
```

`CapabilityInvocation` is frozen and exposes:

- `capability_name`: the canonical validated registry identity.
- `capability`: the exact resolved provider-neutral implementation.
- `model`: the effective model field inherited from or applied to execution
  context.
- `streaming`: `False` for `execute()` and `True` for `stream()`.

Middleware should treat the resolved capability as an identity and should not
mutate implementations. Capability-specific request values remain owned by the
invocation callback; the generic middleware contract does not inspect or
translate protocol payloads.

## Compose middleware

Pass middleware in declaration order when creating a pipeline:

```python
pipeline = CapabilityExecutionPipeline(
    registry,
    middleware=(audit_middleware, timing_middleware),
)

assert pipeline.middleware == (audit_middleware, timing_middleware)
```

The pipeline requires the same sealed `CapabilityRegistry` as before. It copies
the middleware sequence into a tuple so later caller mutation cannot change the
composition. Every entry must structurally implement `execute()` and `stream()`.

Application composition accepts the same ordered sequence:

```python
application = create_application(
    capability_registry=registry,
    capability_middleware=(audit_middleware, timing_middleware),
)
```

The isolated application-owned pipeline remains available at
`application.state.capability_execution_pipeline`. The existing registry and
`chat_capability` compatibility state remain unchanged.

## Ordering and continuation

For middleware declared as `(first, second)`, non-streaming execution enters
`first`, enters `second`, invokes the capability callback, exits `second`, and
then exits `first`. Streaming follows the same nesting for the complete
iterator lifecycle.

Each `call_next` object is valid once. A second call raises `RuntimeError`
before downstream work can run twice. Middleware may omit `call_next` and
return its own result or asynchronous iterator to short-circuit all remaining
layers.

Short-circuiting is an execution primitive, not a routing or policy system.
Middleware remains responsible for returning a value compatible with the
capability-specific caller.

## Streaming ownership

Capability resolution remains eager, while middleware and the capability
stream callback remain lazy until the returned iterator is consumed.

The pipeline tracks every asynchronous iterator created through the chain. It
closes each layer at most once, from the innermost stream outward, after normal
exhaustion, failure, cancellation, generator exit, or consumer early close.
This includes downstream iterators created before a middleware raises or
short-circuits.

Middleware can close the managed iterator returned by `call_next()` in its own
`finally` block; pipeline finalization remains idempotent. Consumers that stop
early must still close the iterator returned by `pipeline.stream()`, as the
runtime SSE transport already does.

Events retain their identities and order. The middleware layer does not
buffer, copy, serialize, interpret, or normalize events.

## Context, failures, and telemetry

The pipeline resolves the capability once, then binds the existing immutable
execution context around middleware entry, continuation, callback execution,
event iteration, and cleanup. Request, execution, provider, and effective model
fields remain available through `get_execution_context()` and are restored
afterward.

Middleware results and errors propagate unchanged. Native cancellation and
generator exit retain their semantics. A cleanup failure does not replace an
already active execution or stream failure; every known stream layer still
receives a cleanup attempt.

Capability middleware adds no automatic log event, metric, or span. The
existing chat decorators continue to emit exactly one capability and provider
lifecycle. A configured middleware may explicitly add its own bounded behavior
without changing the built-in telemetry schema.

## Compatibility and boundaries

An empty middleware sequence is the default for direct pipeline and
`create_application()` callers. Registry lookup, metadata discovery,
`GET /v1/capabilities`, JSON and SSE response contracts, timeouts,
disconnects, graceful shutdown, request IDs, and provider adapters remain
unchanged.

Capability middleware does not define lifecycle hooks, availability, health,
routing, retries, fallback, caching, provider registration, plugin loading,
authentication, authorization, tenant policy, settings, endpoints, Helm values,
Kubernetes resources, CRDs, or operator behavior.

Application-owned lifecycle hooks use the separate
[Capability Lifecycle Management Guide](CAPABILITY_LIFECYCLE.md).
