# Capability Lifecycle Management Guide

Trussium lets registered capabilities optionally own application-scoped
resources through asynchronous startup and shutdown hooks. Lifecycle ownership
is derived once from the sealed capability registry, remains independent of
execution middleware, and does not change ordinary capabilities.

## Optional hook contract

Implement both hooks to opt a registered capability into lifecycle management:

```python
from trussium.app import create_application
from trussium.capabilities import CapabilityRegistry


class EmbeddingsCapability:
    async def startup(self) -> None:
        await self.client.connect()

    async def shutdown(self) -> None:
        await self.client.close()


registry = CapabilityRegistry()
registry.register("embeddings", EmbeddingsCapability())
application = create_application(capability_registry=registry)
```

`LifecycleCapability` is a runtime-checkable structural protocol. A registered
implementation participates only when it implements both `startup()` and
`shutdown()`. Implementations without hooks remain valid, discoverable, and
executable without lifecycle events or adapters.

The registry name is the lifecycle identity. Hooks do not declare another
name, so execution, discovery, failures, and operational events cannot drift
between identities. Names retain the bounded capability-registry validation
and must not contain secrets or request data.

## Composition and ownership

`CapabilityLifecycle` requires a sealed `CapabilityRegistry` and immediately
derives an immutable tuple of `CapabilityLifecycleRegistration` values in
registry order. Later mutation cannot alter the lifecycle plan. Application
composition seals the source registry, creates the plan before applying
execution decorators, and exposes the coordinator as
`application.state.capability_lifecycle`.

This separation is intentional: hooks run on the originally registered
resource owner, while `application.state.capability_registry` contains the
resolved execution implementations and existing chat logging decorator.

The application lifecycle order is:

```text
startup:  runtime services → capabilities → runtime.started
shutdown: capabilities → runtime services → readiness client → tracing
```

If capability startup fails, its completed hooks are rolled back before
already-started runtime services shut down. Capability shutdown failures do not
skip runtime-service, readiness-client, or tracing cleanup.

## Ordering and partial-startup rollback

Participating capabilities start sequentially in registry order and stop once
in reverse order:

```text
startup:  first → second → third
shutdown: third → second → first
```

When one startup hook fails, later hooks do not run. Only hooks whose startup
completed are rolled back, in reverse order. Rollback continues after an
independent error, timeout, or cancellation so all eligible resources receive
one cleanup attempt.

The coordinator does not infer dependencies and does not run hooks
concurrently. Registration order is the explicit ownership order.

## Bounded cleanup

Every rollback and shutdown hook receives the existing positive finite
per-resource deadline from `runtime.service_cleanup_seconds`. The default is
10 seconds:

```bash
export TRUSSIUM_RUNTIME__SERVICE_CLEANUP_SECONDS=5
uv run python -m trussium
```

A timeout cancels the hook, records a stable timeout failure, and continues to
the next capability. This shared setting governs application-owned service and
capability cleanup; it remains separate from provider request deadlines and
the server's active-workload drain deadline.

## States, failures, and cancellation

The coordinator exposes deterministic states:

```text
initialized → starting → started → stopping → stopped
                      ↘ rolling_back → failed
                                  or → failed
```

Startup and shutdown may each run only once. Repeated or out-of-order calls
raise `CapabilityLifecycleStateError` without rerunning hooks.

Hook failures are exposed through `CapabilityLifecycleError`, which inherits
`LifecycleError`. The aggregate contains:

- `phase`: `startup`, `rollback`, or `shutdown`.
- `failures`: an immutable ordered tuple of `CapabilityLifecycleFailure`.
- `code`: a stable value such as `capability_shutdown_failed`.
- `message`: a bounded failure count without raw exception text.

Each failure contains only `capability_name`, `phase`, `code`, and
`error_type`. An original startup exception remains the internal exception
cause but its message is never copied into the public error or structured event.

`asyncio.CancelledError` retains its native identity. Trussium attempts every
eligible bounded rollback or shutdown hook before propagating cancellation.

## Operational events

Every participating hook emits ordered structured events:

| Phase | Events |
| --- | --- |
| Startup | `capability.startup.started`, `.completed`, `.failed`, `.cancelled` |
| Rollback | `capability.rollback.started`, `.completed`, `.failed`, `.timeout`, `.cancelled` |
| Shutdown | `capability.shutdown.started`, `.completed`, `.failed`, `.timeout`, `.cancelled` |

Events may include canonical `capability`, `lifecycle_phase`, `duration_ms`,
`cleanup_timeout_seconds`, `error_code`, `error_type`, and `outcome` fields.
They never serialize implementations, hook results, exception messages,
tracebacks, credentials, endpoints, configuration, prompts, or responses.

## Extension boundary

Use hooks only for resources owned for the complete application lifespan.
Hooks should cooperate with cancellation and release partially initialized
internal resources before raising when possible.

Lifecycle does not define availability, health, routing, retry, fallback,
recovery, provider registration, model discovery, dependency graphs, dynamic
registration, unloading, plugins, endpoints, Kubernetes resources, CRDs, or
operator behavior. Those concerns require separate contracts over the
delivered registry, metadata, execution pipeline, and middleware boundaries.
