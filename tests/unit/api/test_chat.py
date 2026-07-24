"""Tests for chat-completion HTTP endpoints."""

import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamEndEvent,
    ChatStreamEvent,
    ChatStreamStartEvent,
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


def test_chat_completion_documents_json_and_sse_responses() -> None:
    """OpenAPI should describe both supported response content types."""
    app = create_application(
        chat_capability=StubChatCapability(),
    )
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK

    operation = response.json()["paths"]["/v1/chat/completions"]["post"]
    response_content = operation["responses"]["200"]["content"]

    assert "application/json" in response_content
    assert "text/event-stream" in response_content
