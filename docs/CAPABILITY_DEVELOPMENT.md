# Capability Development Guide

A capability is a provider-neutral runtime contract such as chat, embeddings,
reranking, or image generation. It defines normalized requests, responses, and
stream events; providers implement that contract separately. This guide
describes the current explicit composition model for adding a capability.

Provider adapters belong behind a capability. They translate upstream APIs and
normalize provider errors; they must not change the capability identity or
public response contract. Dynamic provider registries and plugin loading remain
future work.

## 1. Define the contract

Create bounded request and response models and a runtime-checkable protocol in
the capability package. Existing contracts are useful references:

| Capability | Protocol | Metadata |
| --- | --- | --- |
| Chat | [`ChatCapability`](../src/trussium/capabilities/chat/capability.py) | `chat.completions` |
| Embeddings | [`EmbeddingsCapability`](../src/trussium/capabilities/embeddings/capability.py) | `embeddings` |
| Images | [`ImageGenerationCapability`](../src/trussium/capabilities/images/capability.py) | `images.generations` |
| Moderation | [`ModerationCapability`](../src/trussium/capabilities/moderation/capability.py) | `moderations` |
| Reranking | [`RerankingCapability`](../src/trussium/capabilities/reranking/capability.py) | `rerankings` |
| Transcription | [`TranscriptionCapability`](../src/trussium/capabilities/transcription/capability.py) | `audio.transcriptions` |
| Video jobs | [`VideoCapability`](../src/trussium/capabilities/videos/capability.py) | `videos` |

Keep the protocol provider-neutral and structural. Do not expose provider SDK
objects, credentials, endpoints, raw errors, or unbounded metadata. Decide
whether streaming is part of the contract and record it in immutable metadata.

## 2. Choose a canonical identity and metadata

Capability names are stable public identities. They must match
`[a-z][a-z0-9_.-]{0,63}`, remain provider-neutral, and never contain a model,
tenant, request ID, URL, or secret. Describe the contract with bounded
`CapabilityMetadata`:

```python
from trussium.capabilities import CapabilityMetadata

CAPABILITY_NAME = "organization.documents"
CAPABILITY_METADATA = CapabilityMetadata(
    name=CAPABILITY_NAME,
    version="v1",
    description="Search organization documents.",
    supports_streaming=False,
)
```

Metadata powers ordered `GET /v1/capabilities` discovery. It does not expose
providers, models, implementation details, health, or availability.

## 3. Register and seal the capability

Application composition owns registration and order. Register the implementation
with matching metadata before sealing the registry:

```python
from trussium.app import create_application
from trussium.capabilities import CapabilityRegistry

registry = CapabilityRegistry()
registry.register(
    CAPABILITY_NAME,
    DocumentsCapability(),
    metadata=CAPABILITY_METADATA,
)
registry.seal()
application = create_application(capability_registry=registry)
```

Registration rejects duplicate identities, invalid names, `None` implementations,
and metadata whose name does not match. Sealing creates the immutable source
boundary; later registration is a configuration error. Preserve declaration
order because discovery, lifecycle, health, and availability reports use it.

## 4. Execute through the pipeline

Use `CapabilityExecutionPipeline` for application-owned execution. It resolves
the canonical capability once, binds immutable execution context, applies
ordered middleware, and preserves results, events, native errors, cancellation,
and stream cleanup:

```python
pipeline = application.state.capability_execution_pipeline
result = await pipeline.execute(
    CAPABILITY_NAME,
    lambda capability: capability.search(request),
    model=None,
)
```

Streaming operations return a lazy async iterator. Consumers must close it on
early exit; the pipeline also closes every known layer after normal completion,
failure, cancellation, or generator exit. Do not buffer or reinterpret events
in generic middleware.

## 5. Add lifecycle, health, or availability only when owned

Capabilities that own a long-lived client may implement both `startup()` and
`shutdown()` to opt into the ordered capability lifecycle. Startup runs in
registry order; shutdown and rollback run in reverse order with bounded
cleanup. Ordinary capabilities need no hooks.

Optional `check_health()` and `check_availability()` hooks are separate,
informational contracts. They use dedicated deadlines, preserve registry order,
normalize failures into bounded states, and never gate liveness, readiness, or
execution. See the [Lifecycle Guide](CAPABILITY_LIFECYCLE.md), [Health Guide](COMPONENT_HEALTH.md),
and [Availability Guide](CAPABILITY_AVAILABILITY.md).

Do not put provider selection, retries, routing, policy, authentication, or
plugin loading into a capability hook. Keep those concerns in their dedicated
runtime layers.

## 6. HTTP and observability boundaries

Add a transport route only when the capability has a stable API contract. The
route should validate protocol input, invoke the registered capability through
the application pipeline, and preserve request correlation, execution context,
structured logging, metrics, tracing, timeouts, and cancellation.

Capability logs and responses may include bounded capability, provider, model,
execution, request, trace, and span identifiers where the existing contract
allows them. Never include prompts, response bodies, credentials, endpoints,
raw provider exception text, or implementation representations.

## Testing checklist

Every capability should have deterministic tests for:

- request and response model validation;
- canonical name and metadata validation;
- registry registration, duplicate rejection, and sealing;
- execution through the pipeline with preserved result identity;
- normalized provider success, malformed response, and error behavior;
- streaming event order, cancellation, and iterator cleanup when applicable;
- lifecycle startup, rollback, and reverse shutdown when applicable;
- bounded health and availability behavior when hooks are implemented;
- HTTP status, JSON/SSE, request-ID, and structured lifecycle contracts.

Use fake providers or transports. Tests must not download models or require
external credentials.

```bash
uv run ruff check src tests
uv run ruff format --check .
uv run mypy src tests
uv run pytest tests/unit/capabilities
uv run pytest
```

## Review checklist

- [ ] The protocol is provider-neutral and structurally typed.
- [ ] The canonical name and metadata are bounded and immutable.
- [ ] Registration occurs before sealing and preserves order.
- [ ] Execution uses the pipeline and preserves context and cleanup.
- [ ] Optional lifecycle, health, and availability hooks remain separate.
- [ ] Provider errors are safe, stable, and categorized.
- [ ] HTTP and observability contracts are tested.
- [ ] No credentials, payloads, or external services are required by tests.

This explicit capability boundary is the foundation for future provider
registries, plugin tooling, and additional protocols without changing existing
runtime contracts.
