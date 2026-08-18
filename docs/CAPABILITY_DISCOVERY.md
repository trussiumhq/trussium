# Capability Metadata and Discovery Guide

Trussium exposes bounded provider-neutral metadata for configured capability
contracts. The same immutable metadata travels with each registry registration,
survives application composition, and powers the read-only external discovery
endpoint.

Discovery answers which capability contracts are configured. It does not
execute them or report whether a provider, model, dependency, or individual
request is currently available.

## Metadata contract

`CapabilityMetadata` is a frozen public value with four fields:

| Field | Required | Contract |
| --- | --- | --- |
| `name` | Yes | Canonical capability identity matching `[a-z][a-z0-9_.-]{0,63}`. |
| `version` | No | Protocol version matching `[a-z0-9][a-z0-9._-]{0,31}`. |
| `description` | No | Stripped public text from 1 to 160 characters without control characters. |
| `supports_streaming` | No | A real boolean feature declaration. |

Optional fields remain `None` when the registration does not make that public
declaration. Absence means unknown or unspecified; it must not be interpreted
as a negative capability claim.

```python
from trussium.capabilities import CapabilityMetadata


metadata = CapabilityMetadata(
    name="organization.embeddings",
    version="v1",
    description="Create normalized embeddings.",
    supports_streaming=False,
)
```

Metadata is deliberately provider-neutral. It must not contain provider or
model identities, endpoints, credentials, tenant details, configuration,
pricing, quotas, implementation types, payloads, or operational failures.

## Register metadata

Pass metadata through the existing registry API:

```python
from trussium.capabilities import CapabilityRegistry


registry = CapabilityRegistry()
registry.register(
    metadata.name,
    embeddings_capability,
    metadata=metadata,
)
```

The metadata name must exactly match the registration name. A mismatch raises
`ValueError` before registry mutation. Duplicate, missing required lookup, and
sealed-mutation behavior retain their existing typed errors.

Existing two-argument callers remain compatible:

```python
registry.register("organization.future", future_capability)
```

Legacy registration creates minimal immutable name-only metadata. It never
guesses a version, description, or streaming declaration.

`CapabilityRegistration(name, capability)` also remains supported. An explicit
third metadata argument is available when constructing immutable registration
values directly.

## Local discovery

The sealed registry exposes metadata without exposing or executing
implementations:

- `registry.metadata` returns an immutable ordered tuple snapshot.
- `registry.get_metadata(name)` returns metadata or `None`.
- `registry.require_metadata(name)` returns metadata or raises
  `CapabilityNotFoundError`.
- `registration.metadata` binds metadata to one implementation registration.

Snapshots preserve insertion order and never change after a later pre-seal
registration. Lookup and metadata discovery remain available after sealing.

## Canonical chat metadata

`CHAT_CAPABILITY_METADATA` describes the delivered `chat.completions` contract:

```python
CapabilityMetadata(
    name="chat.completions",
    version="v1",
    description="Create normalized provider-neutral chat completions.",
    supports_streaming=True,
)
```

The legacy application shortcut and production entry point register this
metadata explicitly. Application composition also binds a registered known chat
implementation to the canonical metadata while applying the existing logging
decorator exactly once. Unknown capability metadata is copied unchanged into
the separate sealed application-owned execution registry.

## External discovery

Use the unauthenticated read-only endpoint:

```http
GET /v1/capabilities
```

A runtime with configured chat execution returns:

```json
{
  "capabilities": [
    {
      "name": "chat.completions",
      "version": "v1",
      "description": "Create normalized provider-neutral chat completions.",
      "supports_streaming": true
    }
  ]
}
```

An empty registry, including the standard provider-free runtime, returns HTTP
200 with:

```json
{"capabilities": []}
```

Capabilities remain in explicit registration order. Optional fields that were
not declared are omitted. The response is generated only from the sealed
application-owned registry and appears in the generated OpenAPI document.

The endpoint performs no inference, provider request, model listing, metadata
probe, health evaluation, readiness evaluation, plugin scan, configuration
lookup, or filesystem/network discovery. It changes neither liveness nor
readiness and exposes no implementation object.

## Compatibility

Metadata and discovery do not change:

- Chat JSON or SSE request and response contracts.
- Provider-neutral errors or the unavailable HTTP 503 response.
- Cancellation, request deadlines, or stream-idle deadlines.
- Request, capability, and provider logs or tracing.
- Dependency readiness or component health reporting.
- Runtime-service lifecycle and registry ownership.
- Metrics labels or collection.
- Container settings, Kubernetes resources, probes, or Helm values.

## Extension boundary

This release provides one ordered collection endpoint. It does not add
per-capability detail endpoints, filtering, pagination, ETags, caching,
mutation, remote control, authentication, authorization, automatic
registration, provider or model discovery, capability availability or health,
version negotiation, aliases, plugins, execution middleware, or an execution
pipeline.

Future features must preserve the bounded metadata validators, canonical
identity, registration order, immutable snapshots, sealed application-owned
source, privacy boundary, and execution compatibility delivered here.
