# Runtime Service Registry Guide

Trussium provides a public application-scoped registry for explicit runtime
service registration, stable lookup, immutable discovery, and deterministic
lifecycle ownership. The registry composes the existing `RuntimeService`
lifecycle contract; it does not discover, instantiate, or inject services.

## Register and compose services

Create a `RuntimeServiceRegistry`, register services in the order they should
start, and pass that registry to the application factory:

```python
from trussium.app import create_application
from trussium.runtime import RuntimeServiceRegistry


class CacheService:
    name = "cache"

    async def startup(self) -> None:
        await self.connect()

    async def shutdown(self) -> None:
        await self.disconnect()


registry = RuntimeServiceRegistry()
cache = registry.register(CacheService())
application = create_application(runtime_service_registry=registry)
```

`register()` returns the supplied service for convenient local composition.
Service names must match `[a-z][a-z0-9_.-]{0,63}`. Registration order becomes
lifecycle startup order; shutdown and partial-startup rollback use the reverse
order described in the [Runtime Service Lifecycle Guide](LIFECYCLE.md).

The existing sequence-based API remains supported:

```python
application = create_application(runtime_services=(CacheService(),))
```

Use either a non-empty `runtime_services` sequence or
`runtime_service_registry`, not both. Applications created without an injected
registry each receive an isolated registry, including when no services are
configured.

## Lookup and discovery

Use `get()` when absence is expected and `require()` when it is a composition
error:

```python
optional_cache = registry.get("cache")
required_cache = registry.require("cache")
```

The following read-only discovery surfaces preserve registration order:

- `registry.names`: an immutable tuple of names.
- `registry.services`: an immutable tuple of service instances.
- `len(registry)`: the registered service count.
- `"cache" in registry`: name membership.
- `tuple(registry)`: ordered service iteration.

Each property access creates an immutable snapshot. A snapshot returned before
a later registration does not change, and the mutable backing mapping is never
exposed.

## Sealing and application ownership

`seal()` is a one-way, idempotent composition transition. It returns the exact
ordered service tuple used to build `RuntimeServiceLifecycle`. The application
factory seals the resolved registry before creating the application and
exposes both objects:

```python
assert application.state.runtime_service_registry is registry
assert application.state.runtime_service_registry.sealed is True
assert application.state.runtime_service_lifecycle.services == registry.services
```

Lookup and discovery remain available after sealing, but later registration
raises `RuntimeServiceRegistrySealedError`. This prevents lifecycle ownership
from diverging from discovery after application composition.

## Errors

Registry-owned failures inherit `RuntimeServiceRegistryError`,
`ConfigurationError`, `TrussiumError`, and `RuntimeError`:

| Error | Code | Condition |
| --- | --- | --- |
| `RuntimeServiceAlreadyRegisteredError` | `runtime_service_already_registered` | A name is already registered. |
| `RuntimeServiceNotFoundError` | `runtime_service_not_found` | `require()` cannot resolve a name. |
| `RuntimeServiceRegistrySealedError` | `runtime_service_registry_sealed` | Registration follows sealing. |

Duplicate registration never replaces or reorders the existing service.
Invalid names retain the lifecycle contract's `ValueError` boundary. Registry
errors contain only validated bounded service names, stable codes, and safe
messages; they do not include service representations, configuration values,
credentials, endpoints, payloads, or exception text.

## Extension boundary

Registration is intentionally explicit and application-scoped. The registry
does not provide unregistration, replacement, hot reload, concurrent startup,
dependency declarations, topological sorting, dependency injection, automatic
discovery, package entry points, plugins, health aggregation, capability
registration, or provider registration. Those concerns require separate
contracts and must not change registry ordering or sealing semantics.

Registered services may independently implement the optional component-health
protocol. The reporter reads the sealed ordered snapshot without adding
registration mutation or lookup behavior; see
[Runtime Component Health Reporting](COMPONENT_HEALTH.md).
