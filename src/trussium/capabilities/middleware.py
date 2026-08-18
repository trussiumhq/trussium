"""Provider-neutral capability execution middleware contracts."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CapabilityInvocation:
    """Immutable metadata for one resolved capability invocation."""

    capability_name: str
    capability: object
    model: str | None
    streaming: bool


@runtime_checkable
class CapabilityExecuteNext(Protocol):
    """Continue one non-streaming capability middleware chain."""

    async def __call__(self) -> object:
        """Invoke the next middleware or resolved capability operation."""
        ...


@runtime_checkable
class CapabilityStreamNext(Protocol):
    """Continue one streaming capability middleware chain."""

    def __call__(self) -> AsyncIterator[object]:
        """Create the next middleware or resolved capability stream."""
        ...


@runtime_checkable
class CapabilityMiddleware(Protocol):
    """Intercept provider-neutral capability execution."""

    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        """Intercept a non-streaming invocation."""
        ...

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ) -> AsyncIterator[object]:
        """Intercept a streaming invocation."""
        ...


__all__ = [
    "CapabilityExecuteNext",
    "CapabilityInvocation",
    "CapabilityMiddleware",
    "CapabilityStreamNext",
]
