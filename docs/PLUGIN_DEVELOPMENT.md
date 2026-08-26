# Plugin Development Kit Guide

ADR-0004 and [ADR-0008](adr/0008-community-provider-plugin-boundary.md) define
Trussium's plugin architecture. This guide turns
that decision into a contributor contract while the runtime still uses explicit
in-repository composition. Plugins are not dynamically loaded or executed from
third-party packages yet.

## Current boundary

Today, a plugin is a separately tested Python package or repository that
implements a documented Trussium extension and is explicitly imported and
registered by an application owner. The runtime does not scan the filesystem,
install packages, execute package entry points, or load untrusted code based on
configuration.

This limitation is intentional: a future loader must define trust, version
compatibility, isolation, permissions, lifecycle, failure handling, and
rollback before it can safely become part of the production entry point.

## Supported extension types

Choose the narrowest extension point:

| Type | Contract and registration boundary |
| --- | --- |
| Provider adapter | Implement an existing provider-neutral capability; follow [Provider Development](PROVIDER_DEVELOPMENT.md). |
| Capability | Define a provider-neutral protocol and metadata; follow [Capability Development](CAPABILITY_DEVELOPMENT.md). |
| Middleware | Implement `CapabilityMiddleware` and pass an ordered tuple to application composition. |
| Runtime service | Implement the application-owned lifecycle contract and register through `RuntimeServiceRegistry`. |
| Tool | Implement an application-declared, allowlisted tool; follow [Tool Execution](TOOL_EXECUTION.md). |

Do not create a plugin to bypass an existing boundary. Plugins must interact
with documented interfaces rather than private runtime modules, route internals,
provider SDK objects, or global state.

## Package layout

A plugin should be independently buildable and testable:

```text
trussium-plugin-example/
├── pyproject.toml
├── README.md
├── src/
│   └── trussium_plugin_example/
│       ├── __init__.py
│       └── capability.py
└── tests/
    └── test_capability.py
```

Keep the package name, import name, and public extension contract distinct from
the canonical capability identity. Pin a compatible Trussium major/minor range
when the plugin depends on a public API, and publish a changelog for contract
changes. Do not rely on import-time side effects.

## Explicit registration

An application owner composes a plugin deliberately:

```python
from trussium.app import create_application
from trussium.capabilities import CapabilityMetadata, CapabilityRegistry
from trussium_plugin_example import ExampleCapability

registry = CapabilityRegistry()
registry.register(
    "organization.example",
    ExampleCapability(),
    metadata=CapabilityMetadata(
        name="organization.example",
        version="v1",
        description="Run the example capability.",
        supports_streaming=False,
    ),
)
registry.seal()
application = create_application(capability_registry=registry)
```

Registration must happen before sealing, preserve declaration order, reject
duplicates, and use bounded provider-neutral names and metadata. A plugin must
not silently replace an existing capability or mutate a registry after
composition.

## Lifecycle and failure behavior

Long-lived plugin resources may implement both `startup()` and `shutdown()`.
Startup follows registration order; shutdown and partial-startup rollback follow
reverse order with bounded cleanup. Hooks must be idempotent, cancellation-aware,
and safe when startup fails halfway through resource creation.

Plugin failures should use the narrowest public Trussium error boundary. Expose
stable codes and safe messages; never copy raw exception text, credentials,
provider responses, local paths, or private endpoints into public errors or
structured events. Native cancellation and unexpected programming errors must
retain their identity.

## Trust and security model

Until a sandboxed loader exists, installing a plugin is equivalent to running
arbitrary code in the runtime process. Application owners must review source,
pin dependencies, verify package provenance, and install only trusted artifacts.

Plugins must:

- receive only explicitly configured clients and registries;
- avoid network, filesystem, subprocess, and credential access unless the
  application intentionally grants it;
- keep provider secrets in the runtime's secret-management boundary;
- avoid logging prompts, responses, tokens, headers, credentials, or raw
  exception messages;
- avoid global monkey-patching, import hooks, and process-wide configuration;
- declare any external network or model requirements in documentation.

The future loader must add package allowlists, signature/provenance policy,
dependency isolation, capability permissions, resource limits, and an audit
trail. A plugin cannot claim those guarantees today.

## Compatibility and loading roadmap

The intended future loading sequence is:

```text
trusted package → compatibility check → explicit allowlist
        → isolated discovery → validated registration → lifecycle startup
```

The mechanism may use package entry points or another discovery protocol, but
the loader must remain separate from plugin implementations. It must reject
unsupported API versions, invalid contracts, duplicate identities, missing
metadata, and unsafe permission requests before application startup completes.

Until that work lands, use a direct import and explicit registration in an
application-owned composition module. Do not add `importlib` scans, automatic
filesystem discovery, or configuration-driven arbitrary imports to the runtime.

## Testing checklist

Every plugin should include deterministic tests for:

- public protocol conformance and bounded metadata;
- registration, duplicate rejection, and sealing;
- successful execution and normalized failure behavior;
- streaming event order and cleanup when applicable;
- lifecycle startup, rollback, shutdown, timeout, and cancellation;
- request, execution, capability, provider, trace, and model correlation;
- absence of credentials, payloads, raw exception text, and private endpoints
  from logs and public responses;
- compatibility with each supported Trussium version range.

Use fake transports and local fixtures. Do not require public providers,
credentials, model downloads, or network access in the default test suite.

```bash
uv run ruff check src tests
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```

## Review checklist

- [ ] The plugin uses a documented public extension point.
- [ ] Registration is explicit and occurs before registry sealing.
- [ ] Canonical identities and metadata are bounded and provider-neutral.
- [ ] Lifecycle hooks are cancellation-aware and release owned resources.
- [ ] Errors and logs preserve privacy and stable code contracts.
- [ ] Dependencies and trust assumptions are documented.
- [ ] Tests are deterministic and do not install or load arbitrary plugins.
- [ ] No dynamic loading was added without a new architecture decision.

For changes to the loading model, permissions, isolation, or compatibility
contract, update [ADR-0008](adr/0008-community-provider-plugin-boundary.md)
before changing runtime behavior.
