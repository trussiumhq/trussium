"""Provider-neutral capability execution pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from math import isfinite
from typing import TYPE_CHECKING, Self, TypeVar, cast

from trussium.capabilities.middleware import (
    CapabilityExecuteNext,
    CapabilityInvocation,
    CapabilityMiddleware,
    CapabilityStreamNext,
)
from trussium.capabilities.registry import CapabilityRegistry
from trussium.runtime.context import bind_execution_context
from trussium.runtime.streaming import close_async_resource

CapabilityResultT = TypeVar("CapabilityResultT")
CapabilityEventT = TypeVar("CapabilityEventT")

if TYPE_CHECKING:
    from trussium.providers.retry import RetryPolicy

_NEXT_ALREADY_CALLED_MESSAGE = "Capability middleware next callable can only be invoked once"


class _ExecuteNext:
    """Enforce single continuation of a non-streaming middleware layer."""

    __slots__ = ("_callback", "_called")

    def __init__(self, callback: CapabilityExecuteNext) -> None:
        """Store the next chain callback."""
        self._callback = callback
        self._called = False

    async def __call__(self) -> object:
        """Continue once or reject duplicate downstream execution."""
        if self._called:
            raise RuntimeError(_NEXT_ALREADY_CALLED_MESSAGE)

        self._called = True
        return await self._callback()


class _ManagedStream(AsyncIterator[object]):
    """Make one middleware or capability stream close at most once."""

    __slots__ = ("_closed", "_stream")

    def __init__(self, stream: AsyncIterator[object]) -> None:
        """Store the stream owned by the execution pipeline."""
        self._stream = stream
        self._closed = False

    def __aiter__(self) -> Self:
        """Return this managed iterator."""
        return self

    async def __anext__(self) -> object:
        """Return the next event unless this layer is already closed."""
        if self._closed:
            raise StopAsyncIteration

        return await anext(self._stream)

    async def aclose(self) -> None:
        """Close the owned stream at most once."""
        if self._closed:
            return

        self._closed = True
        await close_async_resource(self._stream)


class _StreamResources:
    """Track every stream created by one middleware execution."""

    __slots__ = ("_resources",)

    def __init__(self) -> None:
        """Initialize an empty depth-indexed resource collection."""
        self._resources: list[tuple[int, _ManagedStream]] = []

    def manage(
        self,
        stream: AsyncIterator[object],
        *,
        depth: int,
    ) -> _ManagedStream:
        """Return one managed identity and retain its deepest chain position."""
        if isinstance(stream, _ManagedStream):
            for index, (existing_depth, existing) in enumerate(self._resources):
                if existing is stream:
                    if depth > existing_depth:
                        self._resources[index] = (depth, existing)
                    return existing

        managed = _ManagedStream(stream)
        self._resources.append((depth, managed))
        return managed

    async def close(self) -> None:
        """Close all layers from the innermost stream outward."""
        first_error: BaseException | None = None

        for _, resource in sorted(
            self._resources,
            key=lambda item: item[0],
            reverse=True,
        ):
            try:
                await resource.aclose()
            except BaseException as error:
                if first_error is None:
                    first_error = error

        if first_error is not None:
            raise first_error


class _StreamNext:
    """Enforce single continuation of a streaming middleware layer."""

    __slots__ = ("_callback", "_called")

    def __init__(self, callback: CapabilityStreamNext) -> None:
        """Store the next stream-chain callback."""
        self._callback = callback
        self._called = False

    def __call__(self) -> AsyncIterator[object]:
        """Continue once or reject duplicate downstream execution."""
        if self._called:
            raise RuntimeError(_NEXT_ALREADY_CALLED_MESSAGE)

        self._called = True
        return self._callback()


class CapabilityExecutionPipeline:
    """Resolve and execute capabilities through one application-owned boundary."""

    __slots__ = ("_middleware", "_registry", "_retry_policy", "_timeout_seconds")

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        middleware: Sequence[CapabilityMiddleware] = (),
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """Bind execution to an immutable application capability composition.

        Args:
            registry: Sealed application-owned capability registry.
            middleware: Ordered provider-neutral execution middleware.

        Raises:
            ValueError: When the registry remains open for mutation.
            TypeError: When an entry does not implement the middleware contract.
        """
        if not registry.sealed:
            raise ValueError("Capability execution pipeline requires a sealed registry")

        resolved_middleware = tuple(middleware)
        if not all(isinstance(item, CapabilityMiddleware) for item in resolved_middleware):
            raise TypeError("Capability middleware must implement execute() and stream()")
        if timeout_seconds is not None and (not isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("Capability execution timeout must be finite and positive")

        self._registry = registry
        self._middleware = resolved_middleware
        if retry_policy is not None:
            from trussium.providers.retry import RetryPolicy as _RetryPolicy

            if not isinstance(retry_policy, _RetryPolicy):
                raise TypeError("Retry policy must implement the provider retry policy contract")
        self._retry_policy = retry_policy
        self._timeout_seconds = timeout_seconds

    @property
    def registry(self) -> CapabilityRegistry:
        """Return the exact sealed registry owned by this pipeline."""
        return self._registry

    @property
    def middleware(self) -> tuple[CapabilityMiddleware, ...]:
        """Return the immutable ordered middleware composition."""
        return self._middleware

    async def execute(
        self,
        capability_name: str,
        operation: Callable[[object], Awaitable[CapabilityResultT]],
        *,
        model: str | None = None,
    ) -> CapabilityResultT:
        """Execute one non-streaming capability operation.

        Args:
            capability_name: Canonical registered capability identity.
            operation: Capability-specific asynchronous invocation callback.
            model: Optional model identifier for execution context.

        Returns:
            The callback result without copying or normalization.
        """
        capability = self._registry.require(capability_name)

        with bind_execution_context(
            capability=capability_name,
            model=model,
        ) as context:
            invocation = CapabilityInvocation(
                capability_name=capability_name,
                capability=capability,
                model=context.model,
                streaming=False,
            )

            async def invoke(index: int) -> object:
                if index == len(self._middleware):
                    return await operation(capability)

                middleware = self._middleware[index]
                call_next = _ExecuteNext(lambda: invoke(index + 1))
                return await middleware.execute(invocation, call_next)

            if self._retry_policy is None:
                result = await self._invoke_with_timeout(invoke)
            else:
                result = None
                for attempt in range(1, self._retry_policy.max_attempts + 1):
                    try:
                        result = await self._invoke_with_timeout(invoke)
                        break
                    except asyncio.CancelledError:
                        raise
                    except BaseException as error:
                        decision = self._retry_policy.decide(attempt, error)
                        if not decision.retry:
                            raise
                        await asyncio.sleep(decision.delay_seconds)
            return cast(CapabilityResultT, result)

    async def _invoke_with_timeout(self, invoke: Callable[[int], Awaitable[object]]) -> object:
        if self._timeout_seconds is None:
            return await invoke(0)
        async with asyncio.timeout(self._timeout_seconds):
            return await invoke(0)

    def stream(
        self,
        capability_name: str,
        operation: Callable[[object], AsyncIterator[CapabilityEventT]],
        *,
        model: str | None = None,
    ) -> AsyncIterator[CapabilityEventT]:
        """Resolve one capability eagerly and return its contextual stream.

        Args:
            capability_name: Canonical registered capability identity.
            operation: Capability-specific streaming invocation callback.
            model: Optional model identifier for execution context.

        Returns:
            An iterator preserving event identity and execution context.
        """
        capability = self._registry.require(capability_name)
        return self._stream(
            capability_name=capability_name,
            capability=capability,
            operation=operation,
            model=model,
        )

    async def _stream(
        self,
        *,
        capability_name: str,
        capability: object,
        operation: Callable[[object], AsyncIterator[CapabilityEventT]],
        model: str | None,
    ) -> AsyncIterator[CapabilityEventT]:
        """Keep context and cleanup active for the complete iterator lifecycle."""
        with bind_execution_context(
            capability=capability_name,
            model=model,
        ) as context:
            invocation = CapabilityInvocation(
                capability_name=capability_name,
                capability=capability,
                model=context.model,
                streaming=True,
            )
            resources = _StreamResources()
            active_error: BaseException | None = None

            def invoke(index: int) -> AsyncIterator[object]:
                if index == len(self._middleware):
                    return resources.manage(
                        operation(capability),
                        depth=index,
                    )

                middleware = self._middleware[index]
                call_next = _StreamNext(lambda: invoke(index + 1))
                return resources.manage(
                    middleware.stream(invocation, call_next),
                    depth=index,
                )

            try:
                events = invoke(0)
                async for event in events:
                    yield cast(CapabilityEventT, event)
            except BaseException as error:
                active_error = error
                raise
            finally:
                try:
                    await resources.close()
                except BaseException:
                    if active_error is None:
                        raise


__all__ = ["CapabilityExecutionPipeline"]
