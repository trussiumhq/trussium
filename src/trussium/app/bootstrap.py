"""Runtime dependency bootstrap."""

import os

from openai import AsyncOpenAI

from trussium.capabilities.chat import ChatCapability
from trussium.providers.openai import OpenAIChatCapability


def create_chat_capability_from_environment() -> ChatCapability | None:
    """Create the configured runtime chat capability.

    Returns:
        An OpenAI chat capability when an API key is configured, otherwise
        ``None``.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key is None or not api_key.strip():
        return None

    client = AsyncOpenAI(api_key=api_key)

    return OpenAIChatCapability(client)
