"""Tests for the provider-neutral capability execution pipeline."""

import asyncio
from asyncio import CancelledError
from collections.abc import AsyncIterator, Callable
from typing import Self

import pytest

from trussium.capabilities import (
    CapabilityExecutionPipeline,
    CapabilityNotFoundError,
    CapabilityRegistry,
)
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.runtime import (
    ExecutionContext,
    get_execution_context,
    reset_execution_context,
    set_execution_context,
)
from trussium.runtime.streaming import close_async_resource

CAPABILITY_NAME = "test.capability"


class TrackingRegistry(CapabilityRegistry):
    """Record required lookups without changing registry behavior."""

    def __init__(self) -> None:
        """Initialize an empty registry and lookup history."""
        super().__init__()
        self.required_names: list[str] = []

    def require(self, name: str) -> object:
        """Record and perform one required lookup."""
        self.required_names.append(name)
        return super().require(name)


class TrackingStream(AsyncIterator[object]):
    """Yield configured event identities while recording context and cleanup."""

    def __init__(
        self,
        events: list[object],
        *,
        error: BaseException | None = None,
    ) -> None:
        """Initialize stream events and an optional terminal failure."""
        self._events = iter(events)
        self._error = error
        self.contexts: list[ExecutionContext] = []
        self.closed = False
        self.close_context: ExecutionContext | None = None

    def __aiter__(self) -> Self:
        """Return this iterator."""
        return self

    async def __anext__(self) -> object:
        """Return the next event or configured terminal failure."""
        await asyncio.sleep(0)
        self.contexts.append(get_execution_context())

        try:
            return next(self._events)
        except StopIteration:
            if self._error is not None:
                raise self._error from None
            raise StopAsyncIteration from None

    async def aclose(self) -> None:
        """Record deterministic pipeline cleanup."""
        self.closed = True
        self.close_context = get_execution_context()


def create_pipeline(
    capability: object,
) -> tuple[CapabilityExecutionPipeline, TrackingRegistry]:
    """Create a sealed one-capability test pipeline."""
    registry = TrackingRegistry()
    registry.register(CAPABILITY_NAME, capability)
    registry.seal()
    return CapabilityExecutionPipeline(registry), registry


def test_pipeline_requires_and_retains_exact_sealed_registry() -> None:
    """Execution composition should never observe a mutable registry."""
    registry = CapabilityRegistry()

    with pytest.raises(ValueError, match="requires a sealed registry"):
        CapabilityExecutionPipeline(registry)

    registry.seal()
    pipeline = CapabilityExecutionPipeline(registry)

    assert pipeline.registry is registry
    assert pipeline.registry.sealed is True


def test_execute_resolves_once_preserves_identity_and_restores_context() -> None:
    """One execution should bind context and return the exact callback result."""
    capability = object()
    result = object()
    contexts: list[ExecutionContext] = []
    pipeline, registry = create_pipeline(capability)
    outer_context = ExecutionContext(
        request_id="request-123",
        execution_id="execution-123",
        provider="outer-provider",
    )

    async def operation(resolved: object) -> object:
        assert resolved is capability
        contexts.append(get_execution_context())
        await asyncio.sleep(0)
        contexts.append(get_execution_context())
        return result

    async def scenario() -> tuple[object, ExecutionContext]:
        token = set_execution_context(outer_context)
        try:
            actual = await pipeline.execute(
                CAPABILITY_NAME,
                operation,
                model="test-model",
            )
            restored = get_execution_context()
        finally:
            reset_execution_context(token)

        return actual, restored

    actual, restored = asyncio.run(scenario())

    assert actual is result
    assert registry.required_names == [CAPABILITY_NAME]
    assert contexts == [
        ExecutionContext(
            request_id="request-123",
            execution_id="execution-123",
            capability=CAPABILITY_NAME,
            provider="outer-provider",
            model="test-model",
        ),
        ExecutionContext(
            request_id="request-123",
            execution_id="execution-123",
            capability=CAPABILITY_NAME,
            provider="outer-provider",
            model="test-model",
        ),
    ]
    assert restored == outer_context


@pytest.mark.parametrize(
    "error",
    [
        CapabilityExecutionError(
            code="test_failure",
            message="The capability failed.",
            category=CapabilityErrorCategory.UPSTREAM_FAILURE,
        ),
        RuntimeError("private failure"),
        CancelledError(),
    ],
)
def test_execute_propagates_failures_unchanged(error: BaseException) -> None:
    """The generic boundary must not translate normalized or native failures."""
    pipeline, _ = create_pipeline(object())

    async def operation(_: object) -> object:
        raise error

    async def scenario() -> None:
        await pipeline.execute(CAPABILITY_NAME, operation)

    with pytest.raises(type(error)) as captured:
        asyncio.run(scenario())

    assert captured.value is error


def test_execute_preserves_existing_model_when_no_override_is_supplied() -> None:
    """Optional execution fields should enrich rather than erase outer context."""
    pipeline, _ = create_pipeline(object())
    outer_context = ExecutionContext(model="outer-model")
    observed: ExecutionContext | None = None

    async def operation(_: object) -> None:
        nonlocal observed
        observed = get_execution_context()

    async def scenario() -> None:
        token = set_execution_context(outer_context)
        try:
            await pipeline.execute(CAPABILITY_NAME, operation)
        finally:
            reset_execution_context(token)

    asyncio.run(scenario())

    assert observed == ExecutionContext(
        capability=CAPABILITY_NAME,
        model="outer-model",
    )


def test_missing_and_invalid_names_fail_before_invocation() -> None:
    """Registry failures should remain stable and prevent callback execution."""
    registry = CapabilityRegistry()
    registry.seal()
    pipeline = CapabilityExecutionPipeline(registry)
    invoked = False

    async def operation(_: object) -> None:
        nonlocal invoked
        invoked = True

    with pytest.raises(CapabilityNotFoundError):
        asyncio.run(pipeline.execute("missing.capability", operation))

    with pytest.raises(ValueError, match="Capability name must match"):
        asyncio.run(pipeline.execute("Invalid Capability", operation))

    with pytest.raises(CapabilityNotFoundError):
        pipeline.stream("missing.capability", _empty_stream)

    assert invoked is False


def _empty_stream(_: object) -> AsyncIterator[object]:
    """Define a typed empty stream callback."""
    return TrackingStream([])


def test_stream_preserves_event_identity_context_and_cleanup() -> None:
    """Streaming context should remain active until deterministic exhaustion."""
    capability = object()
    first_event = object()
    second_event = object()
    upstream = TrackingStream([first_event, second_event])
    pipeline, registry = create_pipeline(capability)
    outer_context = ExecutionContext(
        request_id="request-stream",
        execution_id="execution-stream",
        provider="outer-provider",
    )

    def operation(resolved: object) -> AsyncIterator[object]:
        assert resolved is capability
        return upstream

    async def scenario() -> tuple[list[object], ExecutionContext]:
        token = set_execution_context(outer_context)
        try:
            events = pipeline.stream(
                CAPABILITY_NAME,
                operation,
                model="stream-model",
            )
            collected = [event async for event in events]
            restored = get_execution_context()
        finally:
            reset_execution_context(token)

        return collected, restored

    collected, restored = asyncio.run(scenario())

    assert collected[0] is first_event
    assert collected[1] is second_event
    assert registry.required_names == [CAPABILITY_NAME]
    assert upstream.closed is True
    assert upstream.close_context == ExecutionContext(
        request_id="request-stream",
        execution_id="execution-stream",
        capability=CAPABILITY_NAME,
        provider="outer-provider",
        model="stream-model",
    )
    assert upstream.contexts == [
        ExecutionContext(
            request_id="request-stream",
            execution_id="execution-stream",
            capability=CAPABILITY_NAME,
            provider="outer-provider",
            model="stream-model",
        ),
        ExecutionContext(
            request_id="request-stream",
            execution_id="execution-stream",
            capability=CAPABILITY_NAME,
            provider="outer-provider",
            model="stream-model",
        ),
        ExecutionContext(
            request_id="request-stream",
            execution_id="execution-stream",
            capability=CAPABILITY_NAME,
            provider="outer-provider",
            model="stream-model",
        ),
    ]
    assert restored == outer_context


def test_stream_closes_upstream_after_consumer_early_close() -> None:
    """A consumer that stops early should release the upstream iterator."""
    first_event = object()
    upstream = TrackingStream([first_event, object()])
    pipeline, _ = create_pipeline(object())

    async def scenario() -> object:
        events = pipeline.stream(CAPABILITY_NAME, lambda _: upstream)
        event = await anext(events)
        await close_async_resource(events)
        return event

    event = asyncio.run(scenario())

    assert event is first_event
    assert upstream.closed is True
    assert upstream.close_context == ExecutionContext(capability=CAPABILITY_NAME)
    assert get_execution_context() == ExecutionContext()


@pytest.mark.parametrize(
    "error_factory",
    [
        lambda: CapabilityExecutionError(
            code="stream_failure",
            message="The capability stream failed.",
            category=CapabilityErrorCategory.UPSTREAM_FAILURE,
        ),
        lambda: RuntimeError("private stream failure"),
        lambda: CancelledError(),
    ],
)
def test_stream_closes_and_propagates_failures_unchanged(
    error_factory: Callable[[], BaseException],
) -> None:
    """Every stream failure path should preserve the error and close upstream."""
    error = error_factory()
    upstream = TrackingStream([], error=error)
    pipeline, _ = create_pipeline(object())

    async def scenario() -> None:
        events = pipeline.stream(CAPABILITY_NAME, lambda _: upstream)
        async for _ in events:
            pass

    with pytest.raises(type(error)) as captured:
        asyncio.run(scenario())

    assert captured.value is error
    assert upstream.closed is True
    assert upstream.close_context == ExecutionContext(capability=CAPABILITY_NAME)


def test_stream_callback_is_invoked_once() -> None:
    """One prepared stream should create exactly one upstream iterator."""
    pipeline, _ = create_pipeline(object())
    invocation_count = 0

    def operation(_: object) -> AsyncIterator[object]:
        nonlocal invocation_count
        invocation_count += 1
        return TrackingStream([])

    async def consume(events: AsyncIterator[object]) -> None:
        async for _ in events:
            pass

    events = pipeline.stream(CAPABILITY_NAME, operation)
    assert invocation_count == 0

    asyncio.run(consume(events))

    assert invocation_count == 1
