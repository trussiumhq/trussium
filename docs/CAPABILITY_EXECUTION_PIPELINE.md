# Capability Execution Pipeline Guide

Trussium provides one public provider-neutral execution boundary on top of the
sealed capability registry. `CapabilityExecutionPipeline` resolves canonical
capability identities, binds the existing immutable execution context, invokes
capability-specific asynchronous work, and finalizes streaming resources.

The pipeline does not define a request model, response model, stream event, or
provider contract. Each capability interface retains those types while sharing
the same resolution and execution behavior.

## Compose a pipeline

A pipeline accepts only a sealed `CapabilityRegistry`:

```python
from trussium.capabilities import CapabilityExecutionPipeline, CapabilityRegistry

registry = CapabilityRegistry()
registry.register("organization.echo", echo_capability)
registry.seal()

pipeline = CapabilityExecutionPipeline(registry)

assert pipeline.registry is registry
assert pipeline.middleware == ()
```

Rejecting an open registry prevents execution from observing registrations that
change after application composition. The `registry` property exposes the exact
sealed registry; it does not create a mutable copy.

`create_application()` always builds an isolated pipeline from its resolved
application-owned registry and stores both as:

```python
application.state.capability_registry
application.state.capability_execution_pipeline
```

The existing `application.state.chat_capability` alias remains available for
compatibility. The chat HTTP API executes through the pipeline-backed registry.

## Execute non-streaming work

`execute()` accepts a canonical name and a capability-specific asynchronous
callback:

```python
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class EchoCapability(Protocol):
    async def echo(self, value: str) -> str: ...

    def stream_echo(self, value: str) -> AsyncIterator[str]: ...


async def invoke(capability: object) -> str:
    if not isinstance(capability, EchoCapability):
        raise TypeError("Configured capability does not implement EchoCapability")

    return await capability.echo("hello")


result = await pipeline.execute(
    "organization.echo",
    invoke,
    model="optional-model-context",
)
```

The registry validates and resolves the name once for that execution. The
pipeline returns the callback result unchanged; it performs no serialization,
normalization, copying, caching, routing, or provider selection.

Known application identities should validate their protocol during composition,
as `chat.completions` already does. The callback remains capability-specific so
future contracts do not depend on chat or provider types.

## Execute streaming work

`stream()` resolves the capability immediately, before the returned iterator is
consumed. This lets protocol adapters preserve pre-stream errors such as the
existing missing-chat HTTP 503 response.

```python
from contextlib import aclosing


def invoke_stream(capability: object) -> AsyncIterator[str]:
    if not isinstance(capability, EchoCapability):
        raise TypeError("Configured capability does not implement EchoCapability")

    return capability.stream_echo("hello")


events = pipeline.stream(
    "organization.echo",
    invoke_stream,
    model="optional-model-context",
)

async with aclosing(events):
    async for event in events:
        consume(event)
```

Events are yielded by identity and in upstream order without buffering or
interpretation. The pipeline closes an upstream iterator exposing `aclose()` or
an asynchronous `close()` after exhaustion, failure, cancellation, generator
exit, or consumer close. Consumers that stop early should close the returned
iterator, as the runtime HTTP streaming response does on every exit path.

## Execution context

Both methods bind the canonical capability name and optional model through the
existing frozen `ExecutionContext`. They preserve outer request, execution,
provider, and model fields that are not replaced.

For streams, context stays active while the callback creates its iterator,
while every event is requested and yielded, and while upstream cleanup runs.
The prior context is restored after the non-streaming call or complete iterator
lifecycle.

This binding is generic execution state, not a new logging or tracing layer.
The existing chat decorators remain responsible for exactly one capability and
provider event/span lifecycle.

## Ordered middleware

Pipelines optionally snapshot an ordered sequence of provider-neutral
middleware. Each layer receives immutable resolved invocation metadata and a
single-use continuation for non-streaming or streaming work. Middleware enters
in declaration order, unwinds in reverse order, and may intentionally
short-circuit downstream execution.

All layers share the execution context described above. Streaming middleware
and every downstream iterator are finalized by the pipeline on every terminal
path. See the [Capability Middleware Guide](CAPABILITY_MIDDLEWARE.md) for the
public contracts, examples, ordering, continuation, and ownership rules.

## Errors and cancellation

The pipeline and optional middleware introduce no normalized execution error
type.

- Invalid names retain the capability-name `ValueError` contract.
- Missing names retain `CapabilityNotFoundError` and its stable
  `capability_not_found` code.
- `CapabilityExecutionError` instances propagate unchanged.
- `CancelledError`, `GeneratorExit`, and unexpected exceptions retain their
  native identities and semantics.
- Calling one middleware continuation more than once raises `RuntimeError`
  before downstream work can execute twice.
- Capability-specific stream error events remain capability-owned values.

The chat API continues to translate a missing `chat.completions` registration
to `chat_capability_unavailable`, map normalized execution categories to the
existing HTTP statuses, and encode normalized stream failures as existing SSE
events.

## Compatibility and ownership boundary

The pipeline changes no registry metadata or `GET /v1/capabilities` response.
Discovery remains execution-free and exposes no provider, model,
implementation, health, availability, or configuration data.

The optional middleware contract adds no automatic lifecycle hooks,
availability, health, routing, retries, fallback, caching, provider registry,
plugin loading, authentication, authorization, endpoint, setting, metric,
event, span, container option, Kubernetes resource, probe, Helm value, CRD, or
operator behavior. Those require separate contracts.
