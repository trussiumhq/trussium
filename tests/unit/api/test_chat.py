"""Tests for chat-completion HTTP endpoints."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import MagicMock

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    CHAT_CAPABILITY_NAME,
    CapabilityExecuteNext,
    CapabilityInvocation,
    CapabilityRegistry,
    CapabilityStreamNext,
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
from trussium.runtime import (
    PROVIDER_REQUEST_TIMEOUT_CODE,
    PROVIDER_REQUEST_TIMEOUT_MESSAGE,
    PROVIDER_STREAM_TIMEOUT_CODE,
    PROVIDER_STREAM_TIMEOUT_MESSAGE,
    TimeoutChatCapability,
)


class StubChatCapability:
    """Deterministic chat capability used by API tests."""

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Return a normalized test response."""
        return ChatCompletionResponse(
            id="chat-test-1",
            provider="stub",
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role=ChatRole.ASSISTANT,
                        content="Hello from the stub provider.",
                    ),
                    finish_reason=FinishReason.STOP,
                )
            ],
            usage=TokenUsage(
                input_tokens=3,
                output_tokens=6,
                total_tokens=9,
            ),
        )

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Return deterministic normalized streaming events."""
        response_id = "chat-test-stream-1"

        yield ChatStreamStartEvent(
            id=response_id,
            provider="stub",
            model=request.model,
        )

        yield ChatStreamDeltaEvent(
            id=response_id,
            content="Hello ",
        )

        yield ChatStreamDeltaEvent(
            id=response_id,
            content="from Trussium.",
        )

        yield ChatStreamEndEvent(
            id=response_id,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=3,
                output_tokens=5,
                total_tokens=8,
            ),
        )


class RecordingCapabilityMiddleware:
    """Record chat invocations while preserving downstream behavior."""

    def __init__(self) -> None:
        """Initialize an empty invocation history."""
        self.invocations: list[CapabilityInvocation] = []

    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        """Record and continue one JSON execution."""
        self.invocations.append(invocation)
        return await call_next()

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ) -> AsyncIterator[object]:
        """Record and continue one SSE execution."""

        async def events() -> AsyncIterator[object]:
            self.invocations.append(invocation)
            async for event in call_next():
                yield event

        return events()


class FailingChatCapability:
    """Chat capability that returns a normalized provider failure."""

    def __init__(
        self,
        error: CapabilityExecutionError,
    ) -> None:
        """Initialize the capability with its configured error."""
        self._error = error

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Raise the configured execution error."""
        _ = request
        raise self._error

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Return the same normalized error as an SSE event."""
        _ = request

        yield ChatStreamErrorEvent(
            id=None,
            code=self._error.code,
            message=self._error.message,
        )


class SlowChatCapability:
    """Delay provider execution for HTTP timeout tests."""

    def __init__(self) -> None:
        """Initialize provider finalization state."""
        self.stream_finalized = False

    async def complete(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Delay a non-streaming completion."""
        await asyncio.sleep(1)
        return await StubChatCapability().complete(request)

    async def stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Start a stream and then stall until its idle deadline."""
        try:
            yield ChatStreamStartEvent(
                id="slow-stream-1",
                provider="slow-provider",
                model=request.model,
            )
            await asyncio.sleep(1)
        finally:
            self.stream_finalized = True


def parse_sse_events(
    body: str,
) -> list[tuple[str, dict[str, object]]]:
    """Parse SSE event names and JSON payloads from a response body."""
    parsed_events: list[tuple[str, dict[str, object]]] = []

    for block in body.strip().split("\n\n"):
        lines = block.splitlines()

        event_name = lines[0].removeprefix("event: ")
        data = lines[1].removeprefix("data: ")

        payload = cast(
            dict[str, object],
            json.loads(data),
        )

        parsed_events.append(
            (
                event_name,
                payload,
            )
        )

    return parsed_events


def test_chat_completion_returns_normalized_response() -> None:
    """A configured capability should execute a non-streaming request."""
    app = create_application(
        chat_capability=StubChatCapability(),
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello.",
                }
            ],
            "stream": False,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "id": "chat-test-1",
        "provider": "stub",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello from the stub provider.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "input_tokens": 3,
            "output_tokens": 6,
            "total_tokens": 9,
        },
    }


def test_registered_chat_capability_is_the_http_execution_source() -> None:
    """Chat execution should resolve the application-owned registry, not its alias."""
    registry = CapabilityRegistry()
    registry.register(CHAT_CAPABILITY_NAME, StubChatCapability())
    app = create_application(capability_registry=registry)
    app.state.chat_capability = None
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "registry-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": False,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["model"] == "registry-model"
    assert registry.sealed is True


def test_non_streaming_chat_executes_through_application_pipeline() -> None:
    """The JSON path should use the composed generic execution boundary."""
    app = create_application(chat_capability=StubChatCapability())
    pipeline = MagicMock(wraps=app.state.capability_execution_pipeline)
    app.state.capability_execution_pipeline = pipeline
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "pipeline-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": False,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    pipeline.execute.assert_called_once()
    assert pipeline.execute.call_args.args[0] == CHAT_CAPABILITY_NAME
    assert pipeline.execute.call_args.kwargs == {"model": "pipeline-model"}


def test_streaming_chat_executes_through_application_pipeline() -> None:
    """The SSE path should use the same composed generic execution boundary."""
    app = create_application(chat_capability=StubChatCapability())
    pipeline = MagicMock(wraps=app.state.capability_execution_pipeline)
    app.state.capability_execution_pipeline = pipeline
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "pipeline-stream-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": True,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    pipeline.stream.assert_called_once()
    assert pipeline.stream.call_args.args[0] == CHAT_CAPABILITY_NAME
    assert pipeline.stream.call_args.kwargs == {"model": "pipeline-stream-model"}


def test_configured_middleware_intercepts_chat_json_and_sse_only() -> None:
    """Both execution modes should share middleware while discovery stays passive."""
    middleware = RecordingCapabilityMiddleware()
    app = create_application(
        chat_capability=StubChatCapability(),
        capability_middleware=(middleware,),
    )
    client = TestClient(app)

    discovery_response = client.get("/v1/capabilities")
    json_response = client.post(
        "/v1/chat/completions",
        json={
            "model": "middleware-json-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": False,
        },
    )
    stream_response = client.post(
        "/v1/chat/completions",
        json={
            "model": "middleware-stream-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": True,
        },
    )

    assert discovery_response.status_code == status.HTTP_200_OK
    assert json_response.status_code == status.HTTP_200_OK
    assert json_response.json()["model"] == "middleware-json-model"
    assert stream_response.status_code == status.HTTP_200_OK
    assert "event: start" in stream_response.text
    assert "event: end" in stream_response.text
    assert [invocation.capability_name for invocation in middleware.invocations] == [
        CHAT_CAPABILITY_NAME,
        CHAT_CAPABILITY_NAME,
    ]
    assert [invocation.model for invocation in middleware.invocations] == [
        "middleware-json-model",
        "middleware-stream-model",
    ]
    assert [invocation.streaming for invocation in middleware.invocations] == [False, True]


def test_chat_completion_streams_normalized_sse_events() -> None:
    """A streaming request should return normalized SSE events."""
    app = create_application(
        chat_capability=StubChatCapability(),
    )
    client = TestClient(app)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello.",
                }
            ],
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"

    assert parse_sse_events(body) == [
        (
            "start",
            {
                "type": "start",
                "id": "chat-test-stream-1",
                "provider": "stub",
                "model": "test-model",
            },
        ),
        (
            "delta",
            {
                "type": "delta",
                "id": "chat-test-stream-1",
                "content": "Hello ",
            },
        ),
        (
            "delta",
            {
                "type": "delta",
                "id": "chat-test-stream-1",
                "content": "from Trussium.",
            },
        ),
        (
            "end",
            {
                "type": "end",
                "id": "chat-test-stream-1",
                "finish_reason": "stop",
                "usage": {
                    "input_tokens": 3,
                    "output_tokens": 5,
                    "total_tokens": 8,
                },
            },
        ),
    ]


def test_chat_completion_returns_normalized_provider_error() -> None:
    """Non-streaming provider failures should use the API error envelope."""
    error_message = (
        "The configured OpenAI project has no available API quota. "
        "Check its billing, credits, and usage limits."
    )

    app = create_application(
        chat_capability=FailingChatCapability(
            CapabilityExecutionError(
                code="openai_quota_exceeded",
                message=error_message,
                category=CapabilityErrorCategory.QUOTA_EXCEEDED,
            )
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello.",
                }
            ],
            "stream": False,
        },
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": {
            "code": "openai_quota_exceeded",
            "message": error_message,
        }
    }
    assert response.content == (
        b'{"detail":{"code":"openai_quota_exceeded","message":'
        b'"The configured OpenAI project has no available API quota. '
        b'Check its billing, credits, and usage limits."}}'
    )


def test_chat_completion_runtime_timeout_returns_504() -> None:
    """A Trussium-enforced provider deadline should use the timeout envelope."""
    capability = TimeoutChatCapability(
        SlowChatCapability(),
        provider_request_seconds=0.001,
        stream_idle_seconds=1,
    )
    app = create_application(chat_capability=capability)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": False,
        },
    )

    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert response.json() == {
        "detail": {
            "code": PROVIDER_REQUEST_TIMEOUT_CODE,
            "message": PROVIDER_REQUEST_TIMEOUT_MESSAGE,
        }
    }


def test_chat_stream_runtime_timeout_emits_normalized_error() -> None:
    """A stalled SSE stream should end with one correlated timeout event."""
    provider = SlowChatCapability()
    capability = TimeoutChatCapability(
        provider,
        provider_request_seconds=1,
        stream_idle_seconds=0.001,
    )
    app = create_application(chat_capability=capability)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello."}],
            "stream": True,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert parse_sse_events(response.text) == [
        (
            "start",
            {
                "type": "start",
                "id": "slow-stream-1",
                "provider": "slow-provider",
                "model": "test-model",
            },
        ),
        (
            "error",
            {
                "type": "error",
                "id": "slow-stream-1",
                "code": PROVIDER_STREAM_TIMEOUT_CODE,
                "message": PROVIDER_STREAM_TIMEOUT_MESSAGE,
            },
        ),
    ]
    assert provider.stream_finalized is True


def test_chat_completion_returns_503_without_provider() -> None:
    """A missing chat capability should produce a service error."""
    app = create_application(
        chat_capability=None,
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello.",
                }
            ],
            "stream": False,
        },
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": {
            "code": "chat_capability_unavailable",
            "message": "No chat provider is configured.",
        }
    }


def test_streaming_returns_503_without_provider() -> None:
    """A streaming request should fail before opening an unavailable stream."""
    app = create_application(
        chat_capability=None,
    )
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello.",
                }
            ],
            "stream": True,
        },
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": {
            "code": "chat_capability_unavailable",
            "message": "No chat provider is configured.",
        }
    }


def test_chat_completion_documents_supported_responses() -> None:
    """OpenAPI should describe success and provider error responses."""
    app = create_application(
        chat_capability=StubChatCapability(),
    )
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK

    operation = response.json()["paths"]["/v1/chat/completions"]["post"]
    responses = operation["responses"]
    response_content = responses["200"]["content"]

    assert "application/json" in response_content
    assert "text/event-stream" in response_content

    assert "400" in responses
    assert "429" in responses
    assert "502" in responses
    assert "503" in responses
    assert "504" in responses
