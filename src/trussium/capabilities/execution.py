"""Provider-neutral capability execution pipeline."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from trussium.capabilities.registry import CapabilityRegistry
from trussium.runtime.context import bind_execution_context
from trussium.runtime.streaming import close_async_resource

CapabilityResultT = TypeVar("CapabilityResultT")
CapabilityEventT = TypeVar("CapabilityEventT")


class CapabilityExecutionPipeline:
    """Resolve and execute capabilities through one application-owned boundary."""

    __slots__ = ("_registry",)

    def __init__(self, registry: CapabilityRegistry) -> None:
        """Bind execution to an immutable application capability composition.

        Args:
            registry: Sealed application-owned capability registry.

        Raises:
            ValueError: When the registry remains open for mutation.
        """
        if not registry.sealed:
            raise ValueError("Capability execution pipeline requires a sealed registry")

        self._registry = registry

    @property
    def registry(self) -> CapabilityRegistry:
        """Return the exact sealed registry owned by this pipeline."""
        return self._registry

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
        ):
            return await operation(capability)

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
        ):
            events = operation(capability)

            try:
                async for event in events:
                    yield event
            finally:
                await close_async_resource(events)


__all__ = ["CapabilityExecutionPipeline"]
