"""Tests for Ollama's OpenAI-compatible chat adapter."""

import asyncio
from typing import cast

import httpx
import pytest
from openai import APIConnectionError, AsyncOpenAI, AuthenticationError
from tests.unit.providers.openai.test_chat import (
    FakeOpenAIClient,
    FakeResponse,
    FakeResponsesResource,
    FakeStreamEvent,
    FakeUsage,
    collect_stream,
    create_http_response,
    create_request,
)

from trussium.capabilities.chat import (
    ChatStreamStartEvent,
)
from trussium.capabilities.errors import (
    CapabilityErrorCategory,
    CapabilityExecutionError,
)
from trussium.providers.ollama import OllamaChatCapability


def create_adapter(resource: FakeResponsesResource) -> OllamaChatCapability:
    """Create an Ollama adapter around the shared compatible fake client."""
    fake_client = FakeOpenAIClient(responses=resource)
    return OllamaChatCapability(cast(AsyncOpenAI, fake_client))


def test_complete_reports_ollama_provider_identity() -> None:
    """Compatible JSON responses should retain Ollama identity."""
    resource = FakeResponsesResource(
        response=FakeResponse(
            id="resp-ollama-1",
            model="llama3.1:8b",
            output_text="Hello from Ollama.",
            usage=FakeUsage(
                input_tokens=4,
                output_tokens=3,
                total_tokens=7,
            ),
        )
    )

    response = asyncio.run(create_adapter(resource).complete(create_request()))

    assert response.provider == "ollama"
    assert response.model == "llama3.1:8b"
    assert response.choices[0].message.content == "Hello from Ollama."
    assert response.usage.total_tokens == 7


def test_stream_reports_ollama_provider_identity() -> None:
    """Compatible stream start events should retain Ollama identity."""
    response = FakeResponse(
        id="resp-ollama-stream",
        model="llama3.1:8b",
        output_text="Hello.",
        usage=FakeUsage(
            input_tokens=2,
            output_tokens=2,
            total_tokens=4,
        ),
    )
    resource = FakeResponsesResource(
        events=[
            FakeStreamEvent(type="response.created", response=response),
            FakeStreamEvent(type="response.completed", response=response),
        ]
    )

    events = asyncio.run(
        collect_stream(
            create_adapter(resource),
            create_request(stream=True),
        )
    )

    assert isinstance(events[0], ChatStreamStartEvent)
    assert events[0].provider == "ollama"
    assert events[0].model == "llama3.1:8b"


def test_authentication_error_uses_ollama_code_and_safe_message() -> None:
    """Compatible SDK failures should identify the configured provider."""
    error = AuthenticationError(
        "Gateway credential rejected.",
        response=create_http_response(status_code=401),
        body={"code": "invalid_api_key"},
    )
    adapter = create_adapter(FakeResponsesResource(error=error))

    with pytest.raises(CapabilityExecutionError) as captured:
        asyncio.run(adapter.complete(create_request()))

    assert captured.value.code == "ollama_authentication_failed"
    assert captured.value.category is CapabilityErrorCategory.UPSTREAM_AUTHENTICATION
    assert captured.value.message == ("Ollama authentication failed. Check the configured API key.")


def test_connection_error_uses_ollama_code_and_safe_message() -> None:
    """Connection failures should not expose SDK or transport details."""
    error = APIConnectionError(
        request=httpx.Request(
            method="POST",
            url="http://ollama.internal:11434/v1/responses",
        )
    )

    assert OllamaChatCapability._api_error_code(error) == "ollama_connection_failed"
    assert OllamaChatCapability._api_error_message(error) == (
        "Trussium could not connect to Ollama."
    )
