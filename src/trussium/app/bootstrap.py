"""Runtime dependency bootstrap."""

import os

from openai import AsyncOpenAI

from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import TimeoutSettings
from trussium.observability import LoggingProviderChatCapability
from trussium.providers.openai import OpenAIChatCapability
from trussium.runtime import TimeoutChatCapability


def create_chat_capability_from_environment(
    *,
    timeouts: TimeoutSettings | None = None,
) -> ChatCapability | None:
    """Create the configured runtime chat capability.

    Args:
        timeouts: Optional provider timeout configuration.

    Returns:
        An OpenAI chat capability when an API key is configured, otherwise
        ``None``.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key is None or not api_key.strip():
        return None

    resolved_timeouts = timeouts or TimeoutSettings()
    client = AsyncOpenAI(api_key=api_key)

    return LoggingProviderChatCapability(
        TimeoutChatCapability(
            OpenAIChatCapability(client),
            provider_request_seconds=resolved_timeouts.provider_request_seconds,
            stream_idle_seconds=resolved_timeouts.stream_idle_seconds,
        ),
        provider=OpenAIChatCapability.provider_name,
    )
