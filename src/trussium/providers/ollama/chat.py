"""Ollama chat capability adapter."""

from trussium.providers.openai import OpenAIChatCapability


class OllamaChatCapability(OpenAIChatCapability):
    """Ollama adapter using its OpenAI-compatible Responses API."""

    provider_name = "ollama"
    provider_display_name = "Ollama"
