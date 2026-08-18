# Runtime Exception Hierarchy

Trussium defines a stable exception hierarchy for failures intentionally
created and classified by the runtime. It gives applications and future
runtime services useful catch boundaries without converting arbitrary Python,
framework, or provider SDK exceptions into public Trussium contracts.

## Hierarchy

```text
RuntimeError
└── TrussiumError
    ├── ConfigurationError
    │   ├── RuntimeServiceRegistryError
    │   │   ├── RuntimeServiceAlreadyRegisteredError
    │   │   ├── RuntimeServiceNotFoundError
    │   │   └── RuntimeServiceRegistrySealedError
    │   └── CapabilityRegistryError
    │       ├── CapabilityAlreadyRegisteredError
    │       ├── CapabilityNotFoundError
    │       ├── CapabilityRegistrySealedError
    │       └── CapabilityContractMismatchError
    └── RuntimeExecutionError
        ├── LifecycleError
        │   ├── RuntimeServiceLifecycleError
        │   └── RuntimeServiceStateError
        ├── DependencyError
        └── CapabilityError
            ├── CapabilityExecutionError
            └── ProviderError
                └── OpenAIProviderError
```

The public domain bases are available from both `trussium` and
`trussium.errors`:

```python
from trussium import ProviderError, TrussiumError

try:
    await run_application()
except ProviderError as error:
    handle_provider_failure(error.code)
except TrussiumError as error:
    handle_runtime_failure(error.code)
```

Concrete compatibility types retain their established modules:

```python
from trussium.capabilities.errors import CapabilityExecutionError
from trussium.providers.openai import OpenAIProviderError
```

Concrete runtime-service lifecycle types are exported from `trussium.runtime`:

```python
from trussium.runtime import RuntimeServiceLifecycleError, RuntimeServiceStateError
```

Runtime-service registry types are also exported from `trussium.runtime`:

```python
from trussium.runtime import RuntimeServiceNotFoundError, RuntimeServiceRegistry
```

Capability-registry types are exported from `trussium.capabilities`:

```python
from trussium.capabilities import CapabilityNotFoundError, CapabilityRegistry
```

## Public attributes

Every `TrussiumError` has:

- `code`: a non-empty stable machine-readable identifier.
- `message`: a non-empty client-safe description.
- `str(error)`: the same client-safe description.

Domain bases supply stable defaults:

| Error | Default code |
| --- | --- |
| `TrussiumError` | `trussium_error` |
| `ConfigurationError` | `configuration_error` |
| `RuntimeExecutionError` | `runtime_execution_error` |
| `LifecycleError` | `lifecycle_error` |
| `DependencyError` | `dependency_error` |
| `CapabilityError` | `capability_error` |
| `ProviderError` | `provider_error` |

Concrete errors should provide a more specific stable code when callers need
to distinguish outcomes. Codes are lowercase snake case, describe a durable
condition rather than an implementation, and must not contain user or provider
data.

`CapabilityExecutionError` continues to add its protocol-neutral
`CapabilityErrorCategory`. Existing HTTP status mapping, JSON details, SSE
events, provider codes, and safe messages are unchanged.

## Catch boundaries

Catch the narrowest type that supports the required recovery:

- `ConfigurationError` for normalized configuration failures owned by
  Trussium. Pydantic `ValidationError` remains Pydantic-owned at settings and
  process-startup boundaries. Runtime-service and capability-registry
  duplicate, required-lookup, and sealed failures inherit this branch; known
  capability contract mismatches do too. Invalid registry names and `None`
  capability implementations remain `ValueError`.
- `LifecycleError` for normalized runtime startup, drain, or shutdown
  failures. Runtime-service hooks normalize startup and cleanup failures into
  bounded aggregate metadata after all eligible hooks run. Existing injected
  readiness and tracing cleanup exceptions retain their established behavior.
- `DependencyError` for normalized external dependency operations. Bounded
  readiness results remain value objects and do not become exceptions.
- `CapabilityExecutionError` when category-aware request handling is needed.
- `ProviderError` for safe provider-adapter failures such as response
  normalization.
- `TrussiumError` only when one policy legitimately handles every owned
  runtime failure.

Do not catch `TrussiumError` as a substitute for handling programmer defects
or arbitrary third-party failures.

## Exceptions outside the hierarchy

The following retain their native identities and semantics:

- `asyncio.CancelledError` and `GeneratorExit`.
- Starlette client disconnects and FastAPI `HTTPException`.
- Pydantic validation failures.
- OpenAI and other provider SDK exceptions before an adapter normalizes them.
- Built-in `TimeoutError` before a runtime deadline boundary normalizes it.
- Unexpected programming errors outside the explicit runtime-service
  lifecycle boundary.

In particular, cancellation must continue to propagate so async tasks and
stream generators terminate correctly.

## Privacy and observability

Codes and messages may appear in client envelopes, logs, metrics, or traces.
They must never include:

- Credentials, authorization headers, or tokens.
- Provider or collector endpoints.
- Prompts, completions, request bodies, or provider responses.
- Request or execution identifiers inside the error code.
- Raw exception text from infrastructure or provider SDKs.

Log the stable code and bounded domain type. Unexpected exceptions may be
recorded through the existing internal exception path, but operational events
must continue to exclude their message and traceback.

## Extending the hierarchy

New runtime-owned errors should:

1. Inherit from the narrowest existing domain base.
2. Use a stable default or concrete code.
3. Expose only a client-safe message.
4. Preserve original exceptions with `raise ... from error` where useful.
5. Leave cancellation and framework control flow untouched.
6. Add inheritance, public-attribute, boundary, and envelope tests.

Adding a new branch or changing inheritance is a public API change. Renaming a
code or changing a client message or transport mapping requires explicit
compatibility review.
