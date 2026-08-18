# Runtime Service Lifecycle Guide

Trussium provides a small public lifecycle contract for application-scoped
runtime services. It defines deterministic asynchronous startup, reverse-order
shutdown, partial-startup rollback, bounded cleanup, and safe operational
failure reporting without introducing the separate runtime service registry.

## Service contract

Implement `RuntimeService` with a stable `name` and asynchronous `startup()`
and `shutdown()` hooks:

```python
from trussium.app import create_application


class CacheService:
    name = "cache"

    async def startup(self) -> None:
        await self.connect()

    async def shutdown(self) -> None:
        await self.disconnect()


cache = CacheService()
application = create_application(runtime_services=(cache,))
```

Service names must match `[a-z][a-z0-9_.-]{0,63}` and must be unique within
one lifecycle plan. Names are operational identifiers, so they must never
contain credentials, endpoints, tenant data, request data, or other secrets.

The application factory copies the supplied sequence into an immutable tuple
and exposes its coordinator as `application.state.runtime_service_lifecycle`.
Existing factory calls that do not supply services remain compatible.

## Ordering

Startup follows declaration order. Shutdown follows the reverse order:

```text
startup:  first → second → third
shutdown: third → second → first
```

`runtime.started` is emitted only after every configured service starts. The
production server has already drained active JSON and SSE work before FastAPI
runs application shutdown. Runtime-service hooks then run before the existing
readiness-client and tracing-exporter cleanup, preserving their established
relative order.

Hooks are sequential by design. The lifecycle layer does not infer service
dependencies, retry hooks, or run hooks concurrently.

## Partial-startup rollback

If a startup hook fails, later services are not started. Only services whose
startup hooks completed are rolled back, in reverse order:

```text
start first ✓ → start second ✓ → start third ✗
                                  │
                                  └→ rollback second → rollback first
```

Rollback continues when one cleanup hook fails or times out. The original
startup failure and bounded rollback failures are then available through one
`RuntimeServiceLifecycleError`.

## Bounded cleanup

Every service shutdown or rollback hook gets its own cleanup deadline. The
default is 10 seconds:

```bash
export TRUSSIUM_RUNTIME__SERVICE_CLEANUP_SECONDS=5
uv run python -m trussium
```

The value must be finite and greater than zero. A timeout cancels that hook,
records a stable timeout failure, and proceeds to the next eligible service.
This deadline is separate from provider execution timeouts and the server's
active-request drain deadline.

## States and failures

`RuntimeServiceLifecycle` exposes these deterministic states:

```text
initialized → starting → started → stopping → stopped
                      ↘ rolling_back → failed
                                  or → failed
```

Startup and shutdown may each run only once. Repeated or out-of-order calls
raise `RuntimeServiceStateError` without re-running hooks.

After every eligible cleanup hook has run, operational failures raise
`RuntimeServiceLifecycleError`. Both concrete errors inherit the public
`LifecycleError`, `RuntimeExecutionError`, `TrussiumError`, and `RuntimeError`
catch boundaries. The aggregate exposes:

- `phase`: `startup`, `rollback`, or `shutdown`.
- `failures`: an immutable tuple of `RuntimeServiceFailure` values.
- `code`: a stable aggregate code such as
  `runtime_service_shutdown_failed`.
- `message`: a bounded count without raw exception text.

Each failure value contains only `service_name`, `phase`, `code`, and
`error_type`. Original startup exceptions remain available as exception causes
for internal diagnosis, but their messages are not copied into the public
error or operational log contract.

`asyncio.CancelledError` is never converted into a Trussium error. Trussium
still attempts eligible bounded rollback or shutdown hooks before propagating
the native cancellation.

## Operational events

Each hook emits ordered structured events:

| Phase | Events |
| --- | --- |
| Startup | `runtime.service.startup.started`, `.completed`, `.failed`, `.cancelled` |
| Rollback | `runtime.service.rollback.started`, `.completed`, `.failed`, `.timeout`, `.cancelled` |
| Shutdown | `runtime.service.shutdown.started`, `.completed`, `.failed`, `.timeout`, `.cancelled` |

Events may include `runtime_service`, `lifecycle_phase`, `duration_ms`,
`cleanup_timeout_seconds`, `error_code`, `error_type`, and `outcome`. They do
not include exception messages, tracebacks, service objects, hook return
values, credentials, endpoints, or request payloads.

## Extension boundary

Use lifecycle hooks only for resources whose ownership matches the application
lifespan. Hooks should be cooperative, idempotent at the resource boundary,
and should release partially initialized internal resources before raising
when possible.

This feature intentionally does not provide service registration, discovery,
dependency ordering, dependency injection, or component health reporting.
Those remain separate runtime-foundation milestones built on this lifecycle
contract.
