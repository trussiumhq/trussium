"""Tests for the OpenAI chat capability adapter."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import cast

import pytest
from openai import AsyncOpenAI

from trussium.capabilities.chat import (
    ChatCapability,
    ChatCompletionRequest,
    ChatMessage,
    ChatRole,
    ChatStreamDeltaEvent,
    ChatStreamEndEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamStartEvent,
    FinishReason,
)
from trussium.providers.openai import (
    OpenAIChatCapability,
    OpenAIProviderError,
)


@dataclass(frozen=True)
class FakeUsage:
    """Fake OpenAI token usage."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class FakeIncompleteDetails:
    """Fake incomplete-response details."""

    reason: str


@dataclass(frozen=True)
class FakeResponseError:
    """Fake OpenAI response error."""

    code: str | None
    message: str


@dataclass(frozen=True)
class FakeResponse:
    """Minimal response used by adapter tests."""

    id: str
    model: str
    output_text: str
    usage: FakeUsage | None
    status: str | None = "completed"
    incomplete_details: FakeIncompleteDetails | None = None
    error: FakeResponseError | None = None


@dataclass(frozen=True)
class FakeStreamEvent:
    """Minimal streaming event used by adapter tests."""

    type: str
    response: FakeResponse | None = None
    delta: str | None = None


class FakeAsyncStream:
    """Asynchronous iterator of fake OpenAI events."""

    def __init__(self, events: list[FakeStreamEvent]) -> None:
        self._events = events

    def __aiter__(self) -> AsyncIterator[FakeStreamEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[FakeStreamEvent]:
        for event in self._events:
            yield event


class FakeResponsesResource:
    """Fake implementation of the OpenAI responses resource."""

    def __init__(
        self,
        *,
        response: FakeResponse | None = None,
        events: list[FakeStreamEvent] | None = None,
    ) -> None:
        self.response = response
        self.events = events or []
        self.last_request: dict[str, object] | None = None

    async def create(self, **kwargs: object) -> object:
        """Return a configured response or stream."""
        self.last_request = kwargs

        if kwargs.get("stream") is True:
            return FakeAsyncStream(self.events)

        if self.response is None:
            raise AssertionError("A fake response was not configured")

        return self.response


@dataclass
class FakeOpenAIClient:
    """Fake object matching the client surface used by the adapter."""

    responses: FakeResponsesResource


def create_request(
    *,
    stream: bool = False,
    role: ChatRole = ChatRole.USER,
) -> ChatCompletionRequest:
    """Create a normalized request for adapter tests."""
    return ChatCompletionRequest(
        model="test-model",
        messages=[
            ChatMessage(
                role=role,
                content="Hello.",
            )
        ],
        temperature=0.4,
        max_output_tokens=100,
        stream=stream,
    )


def create_adapter(
    resource: FakeResponsesResource,
) -> OpenAIChatCapability:
    """Create an adapter using an injected fake client."""
    fake_client = FakeOpenAIClient(responses=resource)
    client = cast(AsyncOpenAI, fake_client)

    return OpenAIChatCapability(client)


async def collect_stream(
    capability: ChatCapability,
    request: ChatCompletionRequest,
) -> list[ChatStreamEvent]:
    """Collect normalized streaming events."""
    return [event async for event in capability.stream(request)]


def test_adapter_satisfies_chat_capability_protocol() -> None:
    """The OpenAI adapter should satisfy the structural protocol."""
    resource = FakeResponsesResource(
        response=FakeResponse(
            id="resp-1",
            model="test-model",
            output_text="Hello from OpenAI.",
            usage=FakeUsage(
                input_tokens=2,
                output_tokens=4,
                total_tokens=6,
            ),
        )
    )
    adapter = create_adapter(resource)

    assert isinstance(adapter, ChatCapability)


def test_complete_normalizes_openai_response() -> None:
    """A successful OpenAI response should become a normalized response."""
    resource = FakeResponsesResource(
        response=FakeResponse(
            id="resp-1",
            model="served-model",
            output_text="Hello from OpenAI.",
            usage=FakeUsage(
                input_tokens=3,
                output_tokens=4,
                total_tokens=7,
            ),
        )
    )
    adapter = create_adapter(resource)

    response = asyncio.run(adapter.complete(create_request()))

    assert response.id == "resp-1"
    assert response.provider == "openai"
    assert response.model == "served-model"
    assert response.choices[0].message.role is ChatRole.ASSISTANT
    assert response.choices[0].message.content == "Hello from OpenAI."
    assert response.choices[0].finish_reason is FinishReason.STOP
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 4
    assert response.usage.total_tokens == 7


def test_complete_translates_request_fields() -> None:
    """Normalized request fields should be passed to OpenAI."""
    resource = FakeResponsesResource(
        response=FakeResponse(
            id="resp-1",
            model="test-model",
            output_text="Hello.",
            usage=FakeUsage(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
            ),
        )
    )
    adapter = create_adapter(resource)

    asyncio.run(adapter.complete(create_request()))

    assert resource.last_request is not None
    assert resource.last_request["model"] == "test-model"
    assert resource.last_request["temperature"] == 0.4
    assert resource.last_request["max_output_tokens"] == 100
    assert resource.last_request["store"] is False
    assert resource.last_request["stream"] is False
    assert resource.last_request["input"] == [
        {
            "role": "user",
            "content": "Hello.",
        }
    ]


def test_complete_normalizes_length_finish_reason() -> None:
    """Maximum output termination should become the normalized length reason."""
    resource = FakeResponsesResource(
        response=FakeResponse(
            id="resp-1",
            model="test-model",
            output_text="Partial response",
            usage=FakeUsage(
                input_tokens=2,
                output_tokens=10,
                total_tokens=12,
            ),
            status="incomplete",
            incomplete_details=FakeIncompleteDetails(reason="max_output_tokens"),
        )
    )
    adapter = create_adapter(resource)

    response = asyncio.run(adapter.complete(create_request()))

    assert response.choices[0].finish_reason is FinishReason.LENGTH


def test_tool_role_is_rejected() -> None:
    """Tool messages should wait for explicit Trussium tool contracts."""
    resource = FakeResponsesResource()
    adapter = create_adapter(resource)

    with pytest.raises(
        OpenAIProviderError,
        match="tool messages are not supported",
    ):
        asyncio.run(
            adapter.complete(
                create_request(role=ChatRole.TOOL),
            )
        )


def test_stream_normalizes_openai_events() -> None:
    """OpenAI streaming events should become normalized events."""
    response = FakeResponse(
        id="resp-stream-1",
        model="served-model",
        output_text="Hello.",
        usage=FakeUsage(
            input_tokens=2,
            output_tokens=2,
            total_tokens=4,
        ),
    )
    resource = FakeResponsesResource(
        events=[
            FakeStreamEvent(
                type="response.created",
                response=response,
            ),
            FakeStreamEvent(
                type="response.output_text.delta",
                delta="Hel",
            ),
            FakeStreamEvent(
                type="response.output_text.delta",
                delta="lo.",
            ),
            FakeStreamEvent(
                type="response.completed",
                response=response,
            ),
        ]
    )
    adapter = create_adapter(resource)

    events = asyncio.run(
        collect_stream(
            adapter,
            create_request(stream=True),
        )
    )

    assert len(events) == 4

    assert isinstance(events[0], ChatStreamStartEvent)
    assert events[0].id == "resp-stream-1"
    assert events[0].provider == "openai"
    assert events[0].model == "served-model"

    assert isinstance(events[1], ChatStreamDeltaEvent)
    assert events[1].content == "Hel"

    assert isinstance(events[2], ChatStreamDeltaEvent)
    assert events[2].content == "lo."

    assert isinstance(events[3], ChatStreamEndEvent)
    assert events[3].finish_reason is FinishReason.STOP
    assert events[3].usage.total_tokens == 4


def test_stream_normalizes_failed_response() -> None:
    """Failed provider events should produce normalized stream errors."""
    response = FakeResponse(
        id="resp-failed-1",
        model="test-model",
        output_text="",
        usage=None,
        status="failed",
        error=FakeResponseError(
            code="server_error",
            message="The provider failed.",
        ),
    )
    resource = FakeResponsesResource(
        events=[
            FakeStreamEvent(
                type="response.created",
                response=response,
            ),
            FakeStreamEvent(
                type="response.failed",
                response=response,
            ),
        ]
    )
    adapter = create_adapter(resource)

    events = asyncio.run(
        collect_stream(
            adapter,
            create_request(stream=True),
        )
    )

    assert len(events) == 2
    assert isinstance(events[1], ChatStreamErrorEvent)
    assert events[1].id == "resp-failed-1"
    assert events[1].code == "server_error"
    assert events[1].message == "The provider failed."
