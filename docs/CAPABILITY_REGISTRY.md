# Core Capability Registry Guide

Trussium provides a public provider-neutral registry for explicit capability
registration, stable lookup, immutable ordered discovery, and deterministic
application composition. The registry replaces per-capability application
lookup without changing the existing capability protocols or execution
behavior.

Registrations can also carry bounded immutable public metadata used for local
and external discovery. See the
[Capability Metadata and Discovery Guide](CAPABILITY_DISCOVERY.md).

## Register capabilities

Use the canonical `chat.completions` identity for the existing
`ChatCapability` contract:

```python
from trussium.app import create_application
from trussium.capabilities import CHAT_CAPABILITY_NAME, CapabilityRegistry


registry = CapabilityRegistry()
registry.register(CHAT_CAPABILITY_NAME, chat_capability)
application = create_application(capability_registry=registry)
```

`register()` returns the supplied implementation for convenient composition.
Names must match `[a-z][a-z0-9_.-]{0,63}`, and implementations must not be
`None`. Names are provider-neutral capability identities, not provider names,
models, routes, tenant identifiers, configuration values, or plugin package
names.

The existing application shortcut remains supported:

```python
application = create_application(chat_capability=chat_capability)
```

Use either `chat_capability` or `capability_registry`, not both. The shortcut
registers the same canonical identity internally and retains its existing
logging and tracing behavior.

## Registration values

`CapabilityRegistration` is a frozen association between a validated name and
one implementation. It can initialize a registry explicitly:

```python
from trussium.capabilities import CapabilityRegistration, CapabilityRegistry


registry = CapabilityRegistry(
    (
        CapabilityRegistration("chat.completions", chat_capability),
        CapabilityRegistration("organization.future", future_capability),
    )
)
```

The core registry intentionally stores implementations as opaque objects. This
allows future provider-neutral protocols to register without making the core
registry depend on every interface. Application composition validates known
identities: an object registered as `chat.completions` must implement the
runtime-checkable `ChatCapability` protocol.

Each registration also contains `CapabilityMetadata`. Existing two-argument
construction creates safe minimal name-only metadata; callers can supply an
explicit third value for public version, description, and streaming support.

## Lookup and discovery

Use `get()` when absence is expected and `require()` when it is a composition
error:

```python
optional_chat = registry.get(CHAT_CAPABILITY_NAME)
required_chat = registry.require(CHAT_CAPABILITY_NAME)
```

The read-only discovery surfaces preserve insertion order:

- `registry.names`: an immutable tuple of capability names.
- `registry.capabilities`: an immutable tuple of implementations.
- `registry.registrations`: an immutable tuple of registration values.
- `registry.metadata`: an immutable tuple of public metadata values.
- `tuple(registry)`: ordered registration iteration.
- `len(registry)`: the registration count.
- `"chat.completions" in registry`: name membership.

Each property access creates a tuple snapshot. A snapshot returned before a
later pre-seal registration does not change, and the mutable backing mapping is
never exposed. `get_metadata()` and `require_metadata()` provide named metadata
lookup. External callers use the separate ordered `GET /v1/capabilities`
transport view rather than receiving registry implementations.

## Sealing and application ownership

`seal()` is a one-way, idempotent composition transition. Lookup and discovery
remain available after sealing, but later registration fails.

The application factory seals the supplied registration source, preserves its
order, validates known protocol contracts, applies the existing chat execution
logging decorator exactly once, and creates a separate sealed application-owned
execution registry:

```python
source_registry = CapabilityRegistry()
source_registry.register(CHAT_CAPABILITY_NAME, chat_capability)

application = create_application(capability_registry=source_registry)

assert source_registry.sealed is True
assert application.state.capability_registry.sealed is True
assert application.state.capability_registry.names == source_registry.names
```

The resolved registry is intentionally an application-owned snapshot rather
than the caller's source object. This prevents composition decorators or later
caller state from changing the execution registry. Unknown future identities
are copied unchanged and remain discoverable.

`application.state.chat_capability` remains a compatibility alias to the
resolved registered chat implementation. Trussium's API dependency resolves
the registry first. Direct state is used only for externally constructed
applications that do not expose a registry.

## Errors

Registry-owned failures inherit `CapabilityRegistryError`,
`ConfigurationError`, `TrussiumError`, and `RuntimeError`:

| Error | Code | Condition |
| --- | --- | --- |
| `CapabilityAlreadyRegisteredError` | `capability_already_registered` | A name is already registered. |
| `CapabilityNotFoundError` | `capability_not_found` | `require()` cannot resolve a name. |
| `CapabilityRegistrySealedError` | `capability_registry_sealed` | Registration follows sealing. |
| `CapabilityContractMismatchError` | `capability_contract_mismatch` | A known identity does not implement its required protocol. |

Duplicate registration never replaces or reorders the original object.
Invalid names and `None` implementations retain the `ValueError` boundary.
Registry errors contain only validated bounded names, stable codes, and safe
messages. They do not contain object representations, provider or model data,
configuration values, credentials, endpoints, payloads, exception text, or
tracebacks.

## Chat execution compatibility

The production entry point now registers its configured provider-backed chat
implementation explicitly. Application composition then preserves the existing
chat capability decorator and execution contracts:

- Normalized JSON and SSE responses.
- Provider-neutral errors and the existing unavailable HTTP 503 response.
- Provider request and stream-idle deadlines.
- Native cancellation and streaming resource cleanup.
- Correlated request, capability, and provider structured events.
- Existing OpenTelemetry span hierarchy and context propagation.
- Existing readiness, metrics, service lifecycle, component health, container,
  and Kubernetes behavior.

No provider configuration is required for the registry. An empty application
registry is valid; the chat endpoint retains
`chat_capability_unavailable` until the canonical chat identity is registered.
Execution through the sealed registry is documented in the
[Capability Execution Pipeline Guide](CAPABILITY_EXECUTION_PIPELINE.md).

## Extension boundary

The core registry is deliberately explicit and application-scoped. It does not
provide unregister, replacement, aliases, priorities, version negotiation, hot
reload, package entry points, automatic discovery, plugins, provider
registration, routing, retry, fallback, dependency graphs, general capability
middleware, lifecycle hooks, availability, health, or recovery actions. One
generic execution pipeline and one ordered metadata collection endpoint are
delivered;
automatic registration, provider/model discovery, detail endpoints, filtering,
pagination, mutation, caching, and remote control remain outside this contract.

Those features require separate contracts. They must preserve registry
identity validation, insertion order, duplicate protection, immutable
snapshots, sealing, safe errors, and the delivered chat compatibility boundary.
