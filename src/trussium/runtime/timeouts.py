"""Provider-neutral chat execution timeout enforcement."""

from asyncio import timeout
from collections.abc import AsyncIterator

from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatStreamErrorEvent,
    ChatStreamEvent,
)
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.runtime.streaming import close_async_resource

PROVIDER_REQUEST_TIMEOUT_CODE = "provider_request_timeout"
PROVIDER_STREAM_TIMEOUT_CODE = "provider_stream_timeout"
PROVIDER_REQUEST_TIMEOUT_MESSAGE = "The provider request timed out."
PROVIDER_STREAM_TIMEOUT_MESSAGE = "The provider stream timed out."


class TimeoutChatCapability:
    """Decorate a chat provider with deterministic runtime timeouts."""

    def __init__(
        self,
        capability: ChatCapability,
        *,
        provider_request_seconds: float,
        stream_idle_seconds: float,
    ) -> None:
        """Initialize provider request and stream-idle deadlines.

        Args:
            capability: Provider chat adapter to decorate.
            provider_request_seconds: Maximum non-streaming execution duration.
            stream_idle_seconds: Maximum wait for each provider stream event.

        Raises:
            ValueError: When either timeout is not positive.
        """
        if provider_request_seconds <= 0:
            raise ValueError("Provider request timeout must be positive")

        if stream_idle_seconds <= 0:
            raise ValueError("Stream idle timeout must be positive")

        self._capability = capability
        self._provider_request_seconds = provider_request_seconds
        self._stream_idle_seconds = stream_idle_seconds

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute a provider request within its configured deadline."""
        try:
            async with timeout(self._provider_request_seconds):
                return await self._capability.complete(request)
        except TimeoutError as error:
            raise CapabilityExecutionError(
                code=PROVIDER_REQUEST_TIMEOUT_CODE,
                message=PROVIDER_REQUEST_TIMEOUT_MESSAGE,
                category=CapabilityErrorCategory.UPSTREAM_TIMEOUT,
            ) from error

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Stream provider events with a deadline reset after every event."""
        events = self._capability.stream(request)
        response_id: str | None = None

        try:
            while True:
                try:
                    async with timeout(self._stream_idle_seconds):
                        event = await anext(events)
                except StopAsyncIteration:
                    return
                except TimeoutError:
                    yield ChatStreamErrorEvent(
                        id=response_id,
                        code=PROVIDER_STREAM_TIMEOUT_CODE,
                        message=PROVIDER_STREAM_TIMEOUT_MESSAGE,
                    )
                    return

                response_id = event.id or response_id
                yield event
        finally:
            await close_async_resource(events)
