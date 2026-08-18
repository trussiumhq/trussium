"""Tests for provider-neutral capability execution middleware."""

import asyncio
from asyncio import CancelledError
from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError
from typing import Self, cast

import pytest

from trussium.capabilities import (
    CapabilityExecuteNext,
    CapabilityExecutionPipeline,
    CapabilityInvocation,
    CapabilityMiddleware,
    CapabilityRegistry,
    CapabilityStreamNext,
)
from trussium.runtime import (
    ExecutionContext,
    get_execution_context,
    reset_execution_context,
    set_execution_context,
)
from trussium.runtime.streaming import close_async_resource

CAPABILITY_NAME = "test.middleware"
NEXT_ERROR = "Capability middleware next callable can only be invoked once"


class RecordingMiddleware:
    """Record ordered entry, exit, invocation, and context observations."""

    def __init__(self, name: str, events: list[str]) -> None:
        """Initialize one named middleware recorder."""
        self.name = name
        self.events = events
        self.invocations: list[CapabilityInvocation] = []
        self.contexts: list[ExecutionContext] = []

    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        """Record execution around the next layer."""
        self.invocations.append(invocation)
        self.contexts.append(get_execution_context())
        self.events.append(f"enter:{self.name}")
        result = await call_next()
        self.events.append(f"exit:{self.name}")
        self.contexts.append(get_execution_context())
        return result

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ) -> AsyncIterator[object]:
        """Record streaming around the next layer."""

        async def events() -> AsyncIterator[object]:
            self.invocations.append(invocation)
            self.contexts.append(get_execution_context())
            self.events.append(f"enter:{self.name}")
            downstream = call_next()
            try:
                async for event in downstream:
                    yield event
            finally:
                self.events.append(f"exit:{self.name}")
                self.contexts.append(get_execution_context())

        return events()


class TrackingStream(AsyncIterator[object]):
    """Yield identities and record deterministic close behavior."""

    def __init__(
        self,
        events: list[object],
        *,
        error: BaseException | None = None,
        close_error: BaseException | None = None,
    ) -> None:
        """Initialize stream data and optional terminal failures."""
        self._events = iter(events)
        self._error = error
        self._close_error = close_error
        self.close_count = 0
        self.close_context: ExecutionContext | None = None

    def __aiter__(self) -> Self:
        """Return this iterator."""
        return self

    async def __anext__(self) -> object:
        """Return the next identity or configured failure."""
        await asyncio.sleep(0)
        try:
            return next(self._events)
        except StopIteration:
            if self._error is not None:
                raise self._error from None
            raise StopAsyncIteration from None

    async def aclose(self) -> None:
        """Record one pipeline-owned close."""
        self.close_count += 1
        self.close_context = get_execution_context()
        if self._close_error is not None:
            raise self._close_error


class DelegatingStream(AsyncIterator[object]):
    """Delegate events without taking ownership of its downstream stream."""

    def __init__(self, downstream: AsyncIterator[object]) -> None:
        """Store the downstream iterator."""
        self._downstream = downstream
        self.close_count = 0
        self.close_context: ExecutionContext | None = None

    def __aiter__(self) -> Self:
        """Return this iterator."""
        return self

    async def __anext__(self) -> object:
        """Delegate one event."""
        return await anext(self._downstream)

    async def aclose(self) -> None:
        """Record cleanup without closing the downstream iterator."""
        self.close_count += 1
        self.close_context = get_execution_context()


class DelegatingMiddleware:
    """Create an independently closable wrapper around the next stream."""

    def __init__(self) -> None:
        """Initialize without a created stream."""
        self.stream_instance: DelegatingStream | None = None

    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        """Pass through non-streaming execution."""
        _ = invocation
        return await call_next()

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ) -> AsyncIterator[object]:
        """Wrap the next stream without owning its cleanup."""
        _ = invocation
        stream = DelegatingStream(call_next())
        self.stream_instance = stream
        return stream


def create_pipeline(
    *middleware: CapabilityMiddleware,
    capability: object | None = None,
) -> CapabilityExecutionPipeline:
    """Create a sealed one-capability middleware pipeline."""
    registry = CapabilityRegistry()
    registry.register(
        CAPABILITY_NAME,
        capability if capability is not None else object(),
    )
    registry.seal()
    return CapabilityExecutionPipeline(registry, middleware=middleware)


def test_public_middleware_contract_and_invocation_are_stable() -> None:
    """The public protocol should be structural and metadata immutable."""
    middleware = RecordingMiddleware("record", [])
    capability = object()
    invocation = CapabilityInvocation(
        capability_name=CAPABILITY_NAME,
        capability=capability,
        model="test-model",
        streaming=False,
    )

    assert isinstance(middleware, CapabilityMiddleware)
    assert invocation.capability_name == CAPABILITY_NAME
    assert invocation.capability is capability
    assert invocation.model == "test-model"
    assert invocation.streaming is False

    with pytest.raises(FrozenInstanceError):
        invocation.model = "changed"  # type: ignore[misc]


def test_pipeline_snapshots_and_validates_ordered_middleware() -> None:
    """Composition should not change when a caller mutates its sequence."""
    first = RecordingMiddleware("first", [])
    configured: list[CapabilityMiddleware] = [first]
    registry = CapabilityRegistry()
    registry.seal()

    pipeline = CapabilityExecutionPipeline(registry, middleware=configured)
    configured.clear()

    assert pipeline.middleware == (first,)

    with pytest.raises(TypeError, match=r"must implement execute.*stream"):
        CapabilityExecutionPipeline(
            registry,
            middleware=(cast(CapabilityMiddleware, object()),),
        )


def test_execute_orders_middleware_preserves_identity_and_context() -> None:
    """Non-streaming middleware should surround one exact callback result."""
    events: list[str] = []
    first = RecordingMiddleware("first", events)
    second = RecordingMiddleware("second", events)
    capability = object()
    result = object()
    pipeline = create_pipeline(first, second, capability=capability)
    outer_context = ExecutionContext(
        request_id="request-middleware",
        execution_id="execution-middleware",
        provider="test-provider",
        model="outer-model",
    )

    async def operation(resolved: object) -> object:
        assert resolved is capability
        events.append("operation")
        assert get_execution_context() == ExecutionContext(
            request_id="request-middleware",
            execution_id="execution-middleware",
            capability=CAPABILITY_NAME,
            provider="test-provider",
            model="override-model",
        )
        return result

    async def scenario() -> tuple[object, ExecutionContext]:
        token = set_execution_context(outer_context)
        try:
            actual = await pipeline.execute(
                CAPABILITY_NAME,
                operation,
                model="override-model",
            )
            restored = get_execution_context()
        finally:
            reset_execution_context(token)
        return actual, restored

    actual, restored = asyncio.run(scenario())

    assert actual is result
    assert restored == outer_context
    assert events == [
        "enter:first",
        "enter:second",
        "operation",
        "exit:second",
        "exit:first",
    ]
    assert first.invocations[0] is second.invocations[0]
    assert first.invocations[0] == CapabilityInvocation(
        capability_name=CAPABILITY_NAME,
        capability=capability,
        model="override-model",
        streaming=False,
    )
    expected_context = ExecutionContext(
        request_id="request-middleware",
        execution_id="execution-middleware",
        capability=CAPABILITY_NAME,
        provider="test-provider",
        model="override-model",
    )
    assert first.contexts == [expected_context, expected_context]
    assert second.contexts == [expected_context, expected_context]


def test_execute_can_short_circuit_without_downstream_invocation() -> None:
    """A middleware result may intentionally bypass later execution."""
    short_circuit_result = object()
    invoked = False

    class ShortCircuitMiddleware(RecordingMiddleware):
        async def execute(
            self,
            invocation: CapabilityInvocation,
            call_next: CapabilityExecuteNext,
        ) -> object:
            _ = invocation, call_next
            self.events.append("short-circuit")
            return short_circuit_result

    events: list[str] = []
    first = ShortCircuitMiddleware("first", events)
    downstream = RecordingMiddleware("downstream", events)
    pipeline = create_pipeline(first, downstream)

    async def operation(_: object) -> object:
        nonlocal invoked
        invoked = True
        return object()

    actual = asyncio.run(pipeline.execute(CAPABILITY_NAME, operation))

    assert actual is short_circuit_result
    assert events == ["short-circuit"]
    assert invoked is False
    assert downstream.invocations == []


def test_execute_rejects_repeated_next_calls_without_duplicate_work() -> None:
    """A middleware cannot invoke downstream execution more than once."""
    operation_count = 0

    class DuplicateNextMiddleware(RecordingMiddleware):
        async def execute(
            self,
            invocation: CapabilityInvocation,
            call_next: CapabilityExecuteNext,
        ) -> object:
            _ = invocation
            await call_next()
            return await call_next()

    pipeline = create_pipeline(DuplicateNextMiddleware("duplicate", []))

    async def operation(_: object) -> object:
        nonlocal operation_count
        operation_count += 1
        return object()

    with pytest.raises(RuntimeError, match=NEXT_ERROR):
        asyncio.run(pipeline.execute(CAPABILITY_NAME, operation))

    assert operation_count == 1


@pytest.mark.parametrize("error", [RuntimeError("private middleware failure"), CancelledError()])
def test_execute_propagates_middleware_failures_unchanged(error: BaseException) -> None:
    """Middleware failures and native cancellation should retain identity."""

    class FailingMiddleware(RecordingMiddleware):
        async def execute(
            self,
            invocation: CapabilityInvocation,
            call_next: CapabilityExecuteNext,
        ) -> object:
            _ = invocation, call_next
            raise error

    pipeline = create_pipeline(FailingMiddleware("failing", []))

    async def scenario() -> object:
        return await pipeline.execute(CAPABILITY_NAME, lambda _: asyncio.sleep(0))

    with pytest.raises(type(error)) as captured:
        asyncio.run(scenario())

    assert captured.value is error


def test_stream_is_lazy_ordered_and_preserves_event_identity() -> None:
    """Middleware and the operation should start only when the stream is consumed."""
    events: list[str] = []
    first = RecordingMiddleware("first", events)
    second = RecordingMiddleware("second", events)
    first_event = object()
    second_event = object()
    upstream = TrackingStream([first_event, second_event])
    operation_count = 0
    pipeline = create_pipeline(first, second)

    def operation(_: object) -> AsyncIterator[object]:
        nonlocal operation_count
        operation_count += 1
        events.append("operation")
        return upstream

    stream = pipeline.stream(CAPABILITY_NAME, operation, model="stream-model")

    assert operation_count == 0
    assert events == []

    collected = asyncio.run(_collect(stream))

    assert collected[0] is first_event
    assert collected[1] is second_event
    assert operation_count == 1
    assert events == [
        "enter:first",
        "enter:second",
        "operation",
        "exit:second",
        "exit:first",
    ]
    assert first.invocations[0] is second.invocations[0]
    assert first.invocations[0].streaming is True
    assert first.invocations[0].model == "stream-model"
    expected_context = ExecutionContext(
        capability=CAPABILITY_NAME,
        model="stream-model",
    )
    assert first.contexts == [expected_context, expected_context]
    assert second.contexts == [expected_context, expected_context]
    assert upstream.close_count == 1
    assert upstream.close_context == expected_context


async def _collect(events: AsyncIterator[object]) -> list[object]:
    """Collect a middleware stream."""
    return [event async for event in events]


def test_stream_closes_every_created_layer_after_consumer_early_close() -> None:
    """Pipeline ownership should not depend on middleware closing downstream."""
    first = DelegatingMiddleware()
    second = DelegatingMiddleware()
    upstream = TrackingStream([object(), object()])
    pipeline = create_pipeline(first, second)

    async def scenario() -> object:
        events = pipeline.stream(CAPABILITY_NAME, lambda _: upstream)
        event = await anext(events)
        await close_async_resource(events)
        return event

    event = asyncio.run(scenario())

    assert event is not None
    assert first.stream_instance is not None
    assert second.stream_instance is not None
    assert first.stream_instance.close_count == 1
    assert second.stream_instance.close_count == 1
    assert upstream.close_count == 1
    expected_context = ExecutionContext(capability=CAPABILITY_NAME)
    assert first.stream_instance.close_context == expected_context
    assert second.stream_instance.close_context == expected_context
    assert upstream.close_context == expected_context
    assert get_execution_context() == ExecutionContext()


def test_stream_can_short_circuit_without_creating_downstream() -> None:
    """A middleware-owned stream may bypass remaining layers and capability work."""
    short_event = object()
    short_stream = TrackingStream([short_event])
    operation_count = 0

    class ShortCircuitMiddleware(RecordingMiddleware):
        def stream(
            self,
            invocation: CapabilityInvocation,
            call_next: CapabilityStreamNext,
        ) -> AsyncIterator[object]:
            _ = invocation, call_next
            return short_stream

    downstream = RecordingMiddleware("downstream", [])
    pipeline = create_pipeline(ShortCircuitMiddleware("short", []), downstream)

    def operation(_: object) -> AsyncIterator[object]:
        nonlocal operation_count
        operation_count += 1
        return TrackingStream([])

    collected = asyncio.run(_collect(pipeline.stream(CAPABILITY_NAME, operation)))

    assert collected == [short_event]
    assert operation_count == 0
    assert downstream.invocations == []
    assert short_stream.close_count == 1


def test_stream_rejects_repeated_next_calls_and_closes_created_downstream() -> None:
    """Repeated stream continuation must not create duplicate capability streams."""
    operation_count = 0
    upstream = TrackingStream([])

    class DuplicateNextMiddleware(RecordingMiddleware):
        def stream(
            self,
            invocation: CapabilityInvocation,
            call_next: CapabilityStreamNext,
        ) -> AsyncIterator[object]:
            _ = invocation
            call_next()
            return call_next()

    pipeline = create_pipeline(DuplicateNextMiddleware("duplicate", []))

    def operation(_: object) -> AsyncIterator[object]:
        nonlocal operation_count
        operation_count += 1
        return upstream

    with pytest.raises(RuntimeError, match=NEXT_ERROR):
        asyncio.run(_collect(pipeline.stream(CAPABILITY_NAME, operation)))

    assert operation_count == 1
    assert upstream.close_count == 1


@pytest.mark.parametrize("error", [RuntimeError("private stream failure"), CancelledError()])
def test_stream_propagates_middleware_failures_and_closes_downstream(
    error: BaseException,
) -> None:
    """A failing middleware should retain error identity and release prior work."""
    upstream = TrackingStream([])

    class FailingStreamMiddleware(RecordingMiddleware):
        def stream(
            self,
            invocation: CapabilityInvocation,
            call_next: CapabilityStreamNext,
        ) -> AsyncIterator[object]:
            _ = invocation

            async def events() -> AsyncIterator[object]:
                call_next()
                yield object()
                raise error

            return events()

    pipeline = create_pipeline(FailingStreamMiddleware("failing", []))

    with pytest.raises(type(error)) as captured:
        asyncio.run(_collect(pipeline.stream(CAPABILITY_NAME, lambda _: upstream)))

    assert captured.value is error
    assert upstream.close_count == 1


def test_stream_preserves_primary_failure_when_cleanup_also_fails() -> None:
    """Cleanup should reach every layer without replacing the active failure."""
    stream_error = RuntimeError("private stream failure")
    close_error = RuntimeError("private close failure")
    upstream = TrackingStream([], error=stream_error, close_error=close_error)
    middleware = DelegatingMiddleware()
    pipeline = create_pipeline(middleware)

    with pytest.raises(RuntimeError) as captured:
        asyncio.run(_collect(pipeline.stream(CAPABILITY_NAME, lambda _: upstream)))

    assert captured.value is stream_error
    assert middleware.stream_instance is not None
    assert middleware.stream_instance.close_count == 1
    assert upstream.close_count == 1
