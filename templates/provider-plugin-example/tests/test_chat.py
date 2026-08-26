"""Test the standalone provider-plugin template without network access."""

import asyncio

from trussium_provider_example import ExampleChatCapability

from trussium.capabilities.chat import ChatCompletionRequest, ChatMessage, ChatRole, ChatStreamEvent


def request(stream: bool = False) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="example-model",
        messages=[ChatMessage(role=ChatRole.USER, content="hello")],
        stream=stream,
    )


def test_complete_returns_normalized_response() -> None:
    response = asyncio.run(ExampleChatCapability().complete(request()))

    assert response.provider == "example"
    assert response.choices[0].message.content.startswith("Example provider")


def test_stream_returns_normalized_lifecycle() -> None:
    async def collect() -> list[ChatStreamEvent]:
        return [event async for event in ExampleChatCapability().stream(request(True))]

    events = asyncio.run(collect())

    assert [event.type for event in events] == ["start", "delta", "end"]
