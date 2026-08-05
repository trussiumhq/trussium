"""Asynchronous streaming resource utilities."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsAsyncClose(Protocol):
    """Resource exposing an asynchronous ``close`` method."""

    async def close(self) -> None:
        """Close the asynchronous resource."""
        ...


@runtime_checkable
class SupportsAsyncGeneratorClose(Protocol):
    """Resource exposing an asynchronous ``aclose`` method."""

    async def aclose(self) -> None:
        """Close the asynchronous generator or iterator."""
        ...


async def close_async_resource(resource: object) -> None:
    """Close an asynchronous resource when it exposes a close method.

    Args:
        resource: Potentially closable asynchronous resource.
    """
    if isinstance(resource, SupportsAsyncGeneratorClose):
        await resource.aclose()
        return

    if isinstance(resource, SupportsAsyncClose):
        await resource.close()
