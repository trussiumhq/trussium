"""OpenAI chat capability adapter."""

from collections.abc import AsyncIterator, Mapping
from typing import Literal

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)
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
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.runtime.streaming import close_async_resource

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
        """Execute and normalize a non-streaming OpenAI response.

        Args:
            request: Normalized chat-completion request.

        Returns:
            Normalized chat-completion response.

        Raises:
            CapabilityExecutionError: When the OpenAI API request fails.
            OpenAIProviderError: When the response cannot be normalized.
        """
        try:
            response = await self._client.responses.create(
                model=request.model,
                input=self._build_input(request.messages),
                max_output_tokens=request.max_output_tokens,
                temperature=request.temperature,
                store=False,
                stream=False,
            )
        except APIError as error:
            raise self._normalize_api_error(error) from error

        return self._normalize_response(response)

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Execute and normalize a streaming OpenAI response."""
        response_id: str | None = None

        try:
            stream = await self._client.responses.create(
                model=request.model,
                input=self._build_input(request.messages),
                max_output_tokens=request.max_output_tokens,
                temperature=request.temperature,
                store=False,
                stream=True,
            )

            try:
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
                            yield ChatStreamErrorEvent(
                                id=None,
                                code="openai_invalid_stream_order",
                                message=(
                                    "OpenAI emitted a text delta before the response start event."
                                ),
                            )
                            return

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

                        try:
                            usage = self._normalize_usage(response)
                        except OpenAIProviderError as error:
                            yield ChatStreamErrorEvent(
                                id=response_id,
                                code="openai_usage_unavailable",
                                message=str(error),
                            )
                            return

                        yield ChatStreamEndEvent(
                            id=response_id,
                            finish_reason=self._normalize_finish_reason(response),
                            usage=usage,
                        )
                        return

                    elif event.type == "response.incomplete":
                        response = event.response

                        if response_id is None:
                            response_id = response.id

                            yield ChatStreamStartEvent(
                                id=response.id,
                                provider=self.provider_name,
                                model=str(response.model),
                            )

                        try:
                            usage = self._normalize_usage(response)
                        except OpenAIProviderError as error:
                            yield ChatStreamErrorEvent(
                                id=response_id,
                                code="openai_response_incomplete",
                                message=str(error),
                            )
                            return

                        yield ChatStreamEndEvent(
                            id=response_id,
                            finish_reason=self._normalize_finish_reason(response),
                            usage=usage,
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
            finally:
                await close_async_resource(stream)

        except APIError as error:
            normalized_error = self._normalize_api_error(error)

            yield ChatStreamErrorEvent(
                id=response_id,
                code=normalized_error.code,
                message=normalized_error.message,
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
    def _normalize_finish_reason(
        response: Response,
    ) -> FinishReason:
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
        """Return a stable code for an unsuccessful OpenAI response."""
        if response.error is None or response.error.code is None:
            return "openai_response_failed"

        return str(response.error.code)

    @staticmethod
    def _response_error_message(response: Response) -> str:
        """Return the provider error message when available."""
        if response.error is None:
            return "OpenAI response failed"

        return response.error.message

    @classmethod
    def _normalize_api_error(
        cls,
        error: APIError,
    ) -> CapabilityExecutionError:
        """Translate an OpenAI SDK error into a capability error."""
        return CapabilityExecutionError(
            code=cls._api_error_code(error),
            message=cls._api_error_message(error),
            category=cls._api_error_category(error),
        )

    @classmethod
    def _api_error_code(cls, error: APIError) -> str:
        """Translate an OpenAI SDK exception into a stable error code."""
        if isinstance(error, AuthenticationError):
            return "openai_authentication_failed"

        if isinstance(error, PermissionDeniedError):
            return "openai_permission_denied"

        if isinstance(error, RateLimitError):
            if cls._is_quota_error(error):
                return "openai_quota_exceeded"

            return "openai_rate_limit_exceeded"

        if isinstance(error, BadRequestError):
            return "openai_invalid_request"

        if isinstance(error, APITimeoutError):
            return "openai_timeout"

        if isinstance(error, APIConnectionError):
            return "openai_connection_failed"

        if isinstance(error, APIStatusError):
            return f"openai_http_{error.status_code}"

        return "openai_api_error"

    @classmethod
    def _api_error_message(cls, error: APIError) -> str:
        """Return a client-safe OpenAI error message."""
        if isinstance(error, AuthenticationError):
            return "OpenAI authentication failed. Check the configured API key."

        if isinstance(error, PermissionDeniedError):
            return "The configured OpenAI project does not have permission to perform this request."

        if isinstance(error, RateLimitError):
            if cls._is_quota_error(error):
                return (
                    "The configured OpenAI project has no available API "
                    "quota. Check its billing, credits, and usage limits."
                )

            return "OpenAI temporarily rejected the request because a rate limit was exceeded."

        if isinstance(error, BadRequestError):
            return "OpenAI rejected the request as invalid."

        if isinstance(error, APITimeoutError):
            return "The request to OpenAI timed out."

        if isinstance(error, APIConnectionError):
            return "Trussium could not connect to OpenAI."

        if isinstance(error, APIStatusError):
            return f"OpenAI returned HTTP status {error.status_code}."

        return "An unexpected OpenAI API error occurred."

    @classmethod
    def _api_error_category(
        cls,
        error: APIError,
    ) -> CapabilityErrorCategory:
        """Classify an OpenAI SDK exception independently of HTTP."""
        if isinstance(error, AuthenticationError):
            return CapabilityErrorCategory.UPSTREAM_AUTHENTICATION

        if isinstance(error, PermissionDeniedError):
            return CapabilityErrorCategory.UPSTREAM_PERMISSION

        if isinstance(error, RateLimitError):
            if cls._is_quota_error(error):
                return CapabilityErrorCategory.QUOTA_EXCEEDED

            return CapabilityErrorCategory.RATE_LIMITED

        if isinstance(error, BadRequestError):
            return CapabilityErrorCategory.INVALID_REQUEST

        if isinstance(error, APITimeoutError):
            return CapabilityErrorCategory.UPSTREAM_TIMEOUT

        if isinstance(error, APIConnectionError):
            return CapabilityErrorCategory.UPSTREAM_CONNECTION

        return CapabilityErrorCategory.UPSTREAM_FAILURE

    @classmethod
    def _is_quota_error(cls, error: APIError) -> bool:
        """Determine whether a rate-limit error represents exhausted quota."""
        provider_code = cls._provider_error_code(error)

        if provider_code in {
            "billing_hard_limit_reached",
            "insufficient_quota",
        }:
            return True

        message = str(error).lower()

        return "quota" in message or "billing" in message

    @staticmethod
    def _provider_error_code(error: APIError) -> str | None:
        """Extract the provider's error code when available."""
        if not isinstance(error, APIStatusError):
            return None

        body = error.body

        if not isinstance(body, Mapping):
            return None

        code = body.get("code")

        if isinstance(code, str):
            return code

        nested_error = body.get("error")

        if isinstance(nested_error, Mapping):
            nested_code = nested_error.get("code")

            if isinstance(nested_code, str):
                return nested_code

        return None
