# Runtime Component Health Reporting

Trussium provides informational health reporting for application-scoped
services in the sealed `RuntimeServiceRegistry`. It gives operators and runtime
composition code a bounded view of component state without changing process
liveness, provider dependency readiness, lifecycle execution, or Kubernetes
traffic decisions.

## Endpoint roles

The three health endpoints have separate contracts:

| Endpoint | Purpose | HTTP behavior |
| --- | --- | --- |
| `GET /health/live` | Prove the process and event loop are serving requests. | Existing HTTP 200 liveness response. |
| `GET /health/ready` | Apply the existing local or optional provider dependency gate. | Existing HTTP 200 or 503 readiness response. |
| `GET /health/components` | Report registered application component states. | Always HTTP 200, for every aggregate state. |

`/health/components` is not a startup, liveness, or readiness probe. A
degraded or unavailable component does not restart a pod, remove it from
service, or change either existing health endpoint. Deployment policy remains
an operator decision outside this reporting API.

## Optional service contract

Existing `RuntimeService` implementations remain valid. A service opts into
health reporting by adding `check_health()`:

```python
from trussium.runtime import RuntimeComponentHealth, RuntimeComponentStatus


class CacheService:
    name = "cache"

    async def startup(self) -> None:
        await self.connect()

    async def shutdown(self) -> None:
        await self.disconnect()

    async def check_health(self) -> RuntimeComponentHealth:
        if self.connection_available:
            return RuntimeComponentHealth(
                name=self.name,
                status=RuntimeComponentStatus.OK,
            )

        return RuntimeComponentHealth(
            name=self.name,
            status=RuntimeComponentStatus.UNAVAILABLE,
            reason="connection_unavailable",
        )
```

The runtime-checkable `RuntimeComponentHealthCheck` protocol is independent of
the lifecycle protocol. Health methods should inspect already-owned local
state and must not start, stop, replace, or reconfigure the service.

## Values and validation

`RuntimeComponentHealth` is frozen and contains only:

- `name`: the exact registered service name.
- `status`: `ok`, `degraded`, `unavailable`, or `unknown`.
- `reason`: a stable bounded code for non-`ok` states.

Names reuse `[a-z][a-z0-9_.-]{0,63}`. Reason codes use
`[a-z][a-z0-9_]{0,63}`. Healthy results must omit a reason; every non-healthy
result must provide one. Codes describe durable conditions and must not contain
exception messages, identifiers, endpoints, credentials, tenant data, or
payload content.

## Reporter and aggregation

`RuntimeComponentHealthReporter` requires a sealed registry. Each report:

1. Takes the registry's immutable insertion-ordered service snapshot.
2. Runs opted-in checks concurrently under independent deadlines.
3. Preserves registry order in the returned immutable tuple.
4. Normalizes owned failure boundaries without exposing raw failures.
5. Computes one aggregate with this precedence:
   `unavailable`, `degraded`, `unknown`, then `ok`.

An empty registry reports `ok`. A registered service without `check_health()`
appears as:

```json
{
  "name": "cache",
  "status": "unknown",
  "reason": "component_health_not_reported"
}
```

The reporter uses these runtime-owned reasons:

| Reason | Meaning |
| --- | --- |
| `component_health_not_reported` | The registered service does not implement the optional protocol. |
| `component_health_timeout` | The check exceeded its runtime-owned deadline. |
| `component_health_check_failed` | The check raised, returned another type, or returned a different service identity. |

Service-specific degraded, unavailable, and unknown states may use their own
validated reason codes.

## Deadline and concurrency

The default per-component deadline is one second. Override it before startup:

```bash
export TRUSSIUM_RUNTIME__COMPONENT_HEALTH_TIMEOUT_SECONDS=0.5
uv run python -m trussium
```

The value must be finite and greater than zero. Independent checks run
concurrently, so deadlines do not accumulate in registry order. The returned
order remains deterministic even when checks complete in another order.

Concurrent calls to one reporter are serialized. A second caller waits for the
in-progress report and then performs a fresh evaluation; results are not
cached. Native `asyncio.CancelledError` always propagates.

## Responses

A mixed report remains HTTP 200:

```json
{
  "status": "degraded",
  "components": [
    {
      "name": "database",
      "status": "ok"
    },
    {
      "name": "cache",
      "status": "degraded",
      "reason": "cache_warming"
    },
    {
      "name": "scheduler",
      "status": "unknown",
      "reason": "component_health_not_reported"
    }
  ]
}
```

The aggregate is a summary, not an exception or readiness decision.

## Operational events

The first observed state and later transitions emit one structured event:

- `runtime.component.health.ok`
- `runtime.component.health.degraded`
- `runtime.component.health.unavailable`
- `runtime.component.health.unknown`

Repeated states do not repeat an event. Records may contain `runtime_service`,
`outcome`, `duration_ms`, `error_code`, and a bounded `error_type` for
runtime-normalized failures. They never contain exception messages, service
objects, health return objects, configuration values, credentials, endpoints,
payloads, response bodies, or tracebacks.

The component endpoint is excluded from workload metrics and request tracing,
like liveness, readiness, and metrics scraping.

## Composition and extension boundary

The application factory constructs one reporter from the exact sealed
registry and exposes it as
`application.state.runtime_component_health_reporter`. Direct users can also
construct a reporter from a sealed registry.

Health reporting does not provide provider metadata checks, capability or
provider registries, dependency graphs, recovery actions, retry, fallback,
circuit breaking, caching, history, persistence, dynamic loading, plugins,
dashboards, alerts, or remote export. New component implementations should
preserve the bounded value, deadline, cancellation, privacy, and informational
endpoint contracts.
