"""OpenAI chat capability adapter."""

from collections.abc import AsyncIterator
from typing import Literal

from openai import AsyncOpenAI
from openai.types.responses import (
    EasyInputMessageParam,
    Response,
    ResponseInputParam,
)

from trussium.capabilities.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamEndEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamStartEvent,
    FinishReason,
    TokenUsage,
)

OpenAIMessageRole = Literal["system", "user", "assistant"]


class OpenAIProviderError(RuntimeError):
    """Raised when an OpenAI response cannot be normalized safely."""


class OpenAIChatCapability:
    """OpenAI implementation of the normalized chat capability."""

    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        """Initialize the adapter with an asynchronous OpenAI client.

        Args:
            client: Configured asynchronous OpenAI client.
        """
        self._client = client

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Execute and normalize a non-streaming OpenAI response."""
        response = await self._client.responses.create(
            model=request.model,
            input=self._build_input(request.messages),
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            store=False,
            stream=False,
        )

        return self._normalize_response(response)

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Execute and normalize a streaming OpenAI response."""
        stream = await self._client.responses.create(
            model=request.model,
            input=self._build_input(request.messages),
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            store=False,
            stream=True,
        )

        response_id: str | None = None

        async for event in stream:
            if event.type == "response.created":
                response = event.response
                response_id = response.id

                yield ChatStreamStartEvent(
                    id=response.id,
                    provider=self.provider_name,
                    model=str(response.model),
                )

            elif event.type == "response.output_text.delta":
                if response_id is None:
                    raise OpenAIProviderError(
                        "OpenAI emitted a text delta before the response start"
                    )

                if event.delta:
                    yield ChatStreamDeltaEvent(
                        id=response_id,
                        content=event.delta,
                    )

            elif event.type == "response.completed":
                response = event.response

                if response_id is None:
                    response_id = response.id

                    yield ChatStreamStartEvent(
                        id=response.id,
                        provider=self.provider_name,
                        model=str(response.model),
                    )

                yield ChatStreamEndEvent(
                    id=response_id,
                    finish_reason=self._normalize_finish_reason(response),
                    usage=self._normalize_usage(response),
                )
                return

            elif event.type == "response.failed":
                response = event.response

                yield ChatStreamErrorEvent(
                    id=response_id or response.id,
                    code=self._response_error_code(response),
                    message=self._response_error_message(response),
                )
                return

    def _normalize_response(
        self,
        response: Response,
    ) -> ChatCompletionResponse:
        """Translate an OpenAI response into a normalized response."""
        self._ensure_successful_response(response)

        content = response.output_text

        if not content:
            raise OpenAIProviderError("OpenAI returned a response without text content")

        return ChatCompletionResponse(
            id=response.id,
            provider=self.provider_name,
            model=str(response.model),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content=content,
                    ),
                    finish_reason=self._normalize_finish_reason(response),
                )
            ],
            usage=self._normalize_usage(response),
        )

    @staticmethod
    def _build_input(
        messages: list[ChatMessage],
    ) -> ResponseInputParam:
        """Translate normalized messages into OpenAI input messages."""
        items: ResponseInputParam = []

        for message in messages:
            item: EasyInputMessageParam = {
                "role": OpenAIChatCapability._normalize_role(message.role),
                "content": message.content,
            }
            items.append(item)

        return items

    @staticmethod
    def _normalize_role(role: ChatRole) -> OpenAIMessageRole:
        """Translate a normalized chat role into an OpenAI role."""
        match role:
            case ChatRole.SYSTEM:
                return "system"
            case ChatRole.USER:
                return "user"
            case ChatRole.ASSISTANT:
                return "assistant"
            case ChatRole.TOOL:
                raise OpenAIProviderError(
                    "OpenAI tool messages are not supported until "
                    "Trussium tool-call contracts are implemented"
                )

    @staticmethod
    def _normalize_usage(response: Response) -> TokenUsage:
        """Translate OpenAI token usage into normalized usage."""
        usage = response.usage

        if usage is None:
            raise OpenAIProviderError("OpenAI response did not include token usage")

        return TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
        )

    @staticmethod
    def _normalize_finish_reason(response: Response) -> FinishReason:
        """Translate OpenAI response status into a finish reason."""
        if response.status == "completed":
            return FinishReason.STOP

        if response.status == "incomplete":
            details = response.incomplete_details

            if details is not None:
                if details.reason == "max_output_tokens":
                    return FinishReason.LENGTH

                if details.reason == "content_filter":
                    return FinishReason.CONTENT_FILTER

            return FinishReason.ERROR

        return FinishReason.ERROR

    @staticmethod
    def _ensure_successful_response(response: Response) -> None:
        """Reject responses that did not complete or return partial output."""
        if response.status in {"completed", "incomplete"}:
            return

        raise OpenAIProviderError(OpenAIChatCapability._response_error_message(response))

    @staticmethod
    def _response_error_code(response: Response) -> str:
        """Return a stable provider-specific error code."""
        if response.error is None or response.error.code is None:
            return "openai_response_failed"

        return response.error.code

    @staticmethod
    def _response_error_message(response: Response) -> str:
        """Return the provider error message where available."""
        if response.error is None:
            return "OpenAI response failed"

        return response.error.message
