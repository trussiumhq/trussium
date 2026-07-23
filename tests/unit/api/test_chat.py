"""Tests for chat-completion HTTP endpoints."""

from collections.abc import AsyncIterator

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    ChatStreamEvent,
    FinishReason,
    TokenUsage,
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
        """Provide the protocol's streaming method for structural typing."""
        del request

        events: list[ChatStreamEvent] = []

        for event in events:
            yield event


def test_chat_completion_returns_normalized_response() -> None:
    """A configured capability should execute the request."""
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


def test_chat_completion_returns_503_without_provider() -> None:
    """A missing chat capability should produce a service error."""
    app = create_application(chat_capability=None)
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
        },
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "detail": {
            "code": "chat_capability_unavailable",
            "message": "No chat provider is configured.",
        }
    }


def test_chat_completion_rejects_streaming_requests() -> None:
    """HTTP streaming should remain disabled until SSE is implemented."""
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
            "stream": True,
        },
    )

    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert response.json() == {
        "detail": {
            "code": "streaming_not_implemented",
            "message": (
                "HTTP streaming is not implemented yet. Submit the request with stream=false."
            ),
        }
    }
