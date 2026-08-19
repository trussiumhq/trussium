# Capability Availability Reporting Guide

Trussium exposes an informational, provider-neutral view of whether registered
capabilities can currently accept execution. Reporting is derived from the
sealed source registry, preserves registration order, and does not change
execution, routing, liveness, or readiness.

## Availability contract

Every registered capability is `available` by default. A capability can opt
into an active check by structurally implementing the asynchronous
`CapabilityAvailabilityCheck` protocol:

```python
from trussium.capabilities import (
    CapabilityAvailability,
    CapabilityAvailabilityStatus,
)


class EmbeddingsCapability:
    async def check_availability(self) -> CapabilityAvailability:
        if await self.client.is_ready():
            return CapabilityAvailability(
                name="organization.embeddings",
                status=CapabilityAvailabilityStatus.AVAILABLE,
            )

        return CapabilityAvailability(
            name="organization.embeddings",
            status=CapabilityAvailabilityStatus.UNAVAILABLE,
            reason="provider_offline",
        )
```

`CapabilityAvailability` is frozen and contains:

| Field | Contract |
| --- | --- |
| `name` | The canonical registered capability name. |
| `status` | `available` or `unavailable`. |
| `reason` | Absent for `available`; required for `unavailable` and matching `[a-z][a-z0-9_]{0,63}`. |

The returned name must exactly match the registry identity. A check cannot
rename a capability or return implementation, provider, model, endpoint,
credential, request, or response data.

## Reporting behavior

`CapabilityAvailabilityReporter` requires a sealed `CapabilityRegistry` and
retains that exact registry as its reporting source. Application composition
creates it before chat execution decorators are applied, so checks run on the
original registered resource owner while execution continues through the
separate application-owned execution registry.

Each report:

- Starts a fresh check for every participating capability; results are not cached.
- Runs independent checks concurrently.
- Preserves registration order regardless of completion order.
- Serializes concurrent callers so checks from separate reports do not overlap.
- Reports ordinary capabilities as `available` without probing them.
- Aggregates to `unavailable` when any capability is unavailable; otherwise it
  aggregates to `available`, including for an empty registry.

The reporter never executes a capability request and never changes registry,
lifecycle, middleware, or execution-pipeline state.

## Bounded failure handling

Each active check has a separate positive finite deadline. The default is one
second and can be configured with:

```bash
export TRUSSIUM_RUNTIME__CAPABILITY_AVAILABILITY_TIMEOUT_SECONDS=0.5
```

The typed setting is
`runtime.capability_availability_timeout_seconds`. It is independent of
provider request, stream-idle, dependency-readiness, component-health,
lifecycle-cleanup, and graceful-shutdown deadlines.

Owned check failures become stable unavailable values:

| Condition | Reason |
| --- | --- |
| Check exceeds its deadline | `capability_availability_timeout` |
| Check raises, returns another type, or returns a mismatched name | `capability_availability_check_failed` |

Raw exception messages are never exposed. Native `asyncio.CancelledError`
retains its identity and is not normalized into an availability response.

## HTTP endpoint

Use the read-only endpoint:

```http
GET /v1/capabilities/availability
```

An unavailable capability still returns HTTP 200 because this is an
informational report:

```json
{
  "status": "unavailable",
  "capabilities": [
    {
      "name": "organization.embeddings",
      "status": "unavailable",
      "reason": "provider_offline"
    },
    {
      "name": "chat.completions",
      "status": "available"
    }
  ]
}
```

An empty registry returns:

```json
{"status":"available","capabilities":[]}
```

The route uses the normal request-correlation, structured-request-logging,
metrics, and tracing middleware. It appears in OpenAPI and is not a Kubernetes
startup, liveness, or readiness probe.

## Operational events

The reporter emits an event only when a capability's bounded state or reason
changes:

| Event | Level |
| --- | --- |
| `capability.availability.available` | INFO |
| `capability.availability.unavailable` | WARNING |

Events may contain canonical `capability`, bounded `outcome`, `duration_ms`,
stable `error_code`, and error class in `error_type`. They contain no check
result object, exception message, traceback, endpoint, credential,
configuration, prompt, or completion. Repeated identical reports do not repeat
the transition event.

## Boundaries

Availability reporting does not:

- Block or permit execution.
- Change HTTP status codes for chat or other capabilities.
- Affect `/health/live`, `/health/ready`, or `/health/components`.
- Define capability health, quality, latency, capacity, quotas, or correctness.
- Select a provider or model, route, retry, fall back, recover, or unload.
- Discover remote providers, models, plugins, or unregistered capabilities.
- Add Kubernetes probes, resources, ports, permissions, or an operator.

Future capability health and routing work may consume the same canonical
identity boundary, but must remain separate from this informational contract.
