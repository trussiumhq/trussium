"""Deterministic chat capability used as a provider-plugin template."""

from collections.abc import AsyncIterator

from trussium.capabilities.chat import (
    ChatCapability,
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


class ExampleChatCapability(ChatCapability):
    """Replace the deterministic response with a real provider transport."""

    provider_name = "example"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Return a normalized response without external network access."""
        response_id = f"example-{request.model}"
        content = f"Example provider received {len(request.messages)} message(s)."
        usage = TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)
        return ChatCompletionResponse(
            id=response_id,
            provider=self.provider_name,
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role=ChatRole.ASSISTANT, content=content),
                    finish_reason=FinishReason.STOP,
                )
            ],
            usage=usage,
        )

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatStreamEvent]:
        """Yield the same normalized lifecycle as a real streaming adapter."""
        response_id = f"example-{request.model}"
        content = f"Example provider received {len(request.messages)} message(s)."
        yield ChatStreamStartEvent(id=response_id, provider=self.provider_name, model=request.model)
        yield ChatStreamDeltaEvent(id=response_id, content=content)
        yield ChatStreamEndEvent(
            id=response_id,
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0),
        )
