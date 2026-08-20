"""Runtime dependency bootstrap."""

import os
from typing import Final

import httpx
from openai import AsyncOpenAI
from opentelemetry.trace import Tracer

from trussium.capabilities.chat import ChatCapability
from trussium.capabilities.embeddings import EmbeddingsCapability
from trussium.capabilities.images import ImageGenerationCapability
from trussium.capabilities.moderation import ModerationCapability
from trussium.capabilities.reranking import RerankingCapability
from trussium.capabilities.transcription import TranscriptionCapability
from trussium.config.settings import (
    ProviderName,
    ProviderSettings,
    ReadinessSettings,
    RerankingSettings,
    TimeoutSettings,
)
from trussium.observability import LoggingProviderChatCapability
from trussium.providers.ollama import OllamaChatCapability
from trussium.providers.openai import (
    OpenAIChatCapability,
    OpenAICompatibleProviderHealthCheck,
    OpenAIEmbeddingsCapability,
    OpenAIImageGenerationCapability,
    OpenAIModerationCapability,
    OpenAITranscriptionCapability,
)
from trussium.providers.tei import TEIRerankingCapability
from trussium.runtime import (
    DependencyFailureReason,
    DependencyHealthCheck,
    TimeoutChatCapability,
    UnavailableDependencyHealthCheck,
)

OLLAMA_DEFAULT_BASE_URL: Final = "http://127.0.0.1:11434/v1"
OLLAMA_DEFAULT_API_KEY: Final = "ollama"


def create_chat_capability_from_environment(
    *,
    provider: ProviderSettings | None = None,
    timeouts: TimeoutSettings | None = None,
    tracer: Tracer | None = None,
) -> ChatCapability | None:
    """Create the configured runtime chat capability.

    Args:
        provider: Optional provider configuration.
        timeouts: Optional provider timeout configuration.
        tracer: Optional application-owned OpenTelemetry tracer.

    Returns:
        The configured provider capability, or ``None`` when OpenAI is
        selected without a credential.
    """
    resolved_provider = provider or ProviderSettings()
    api_key = _resolve_api_key(resolved_provider)

    if api_key is None:
        return None

    resolved_timeouts = timeouts or TimeoutSettings()
    base_url = _resolve_base_url(resolved_provider)
    client = (
        AsyncOpenAI(api_key=api_key, base_url=base_url)
        if base_url is not None
        else AsyncOpenAI(api_key=api_key)
    )
    adapter = (
        OllamaChatCapability(client)
        if resolved_provider.name is ProviderName.OLLAMA
        else OpenAIChatCapability(client)
    )

    return LoggingProviderChatCapability(
        TimeoutChatCapability(
            adapter,
            provider_request_seconds=resolved_timeouts.provider_request_seconds,
            stream_idle_seconds=resolved_timeouts.stream_idle_seconds,
        ),
        provider=adapter.provider_name,
        tracer=tracer,
    )


def create_embeddings_capability_from_environment(
    *,
    provider: ProviderSettings | None = None,
) -> EmbeddingsCapability | None:
    """Create the configured OpenAI-compatible embeddings capability."""
    resolved_provider = provider or ProviderSettings()
    api_key = _resolve_api_key(resolved_provider)
    if api_key is None:
        return None

    base_url = _resolve_base_url(resolved_provider)
    client = (
        AsyncOpenAI(api_key=api_key, base_url=base_url)
        if base_url is not None
        else AsyncOpenAI(api_key=api_key)
    )
    return OpenAIEmbeddingsCapability(client)


def create_image_generation_capability_from_environment(
    *,
    provider: ProviderSettings | None = None,
) -> ImageGenerationCapability | None:
    """Create the configured OpenAI image-generation capability."""
    resolved_provider = provider or ProviderSettings()
    api_key = _resolve_api_key(resolved_provider)
    if api_key is None:
        return None
    base_url = _resolve_base_url(resolved_provider)
    client = (
        AsyncOpenAI(api_key=api_key, base_url=base_url)
        if base_url is not None
        else AsyncOpenAI(api_key=api_key)
    )
    return OpenAIImageGenerationCapability(client)


def create_moderation_capability_from_environment(
    *,
    provider: ProviderSettings | None = None,
) -> ModerationCapability | None:
    """Create the configured OpenAI moderation capability."""
    resolved_provider = provider or ProviderSettings()
    api_key = _resolve_api_key(resolved_provider)
    if api_key is None:
        return None
    base_url = _resolve_base_url(resolved_provider)
    client = (
        AsyncOpenAI(api_key=api_key, base_url=base_url)
        if base_url is not None
        else AsyncOpenAI(api_key=api_key)
    )
    return OpenAIModerationCapability(client)


def create_reranking_capability_from_environment(
    *, reranking: RerankingSettings | None = None
) -> RerankingCapability | None:
    """Create the configured privately hosted TEI reranking capability."""
    resolved = reranking or RerankingSettings()
    if resolved.base_url is None:
        return None
    headers = (
        {"Authorization": f"Bearer {resolved.api_key.get_secret_value()}"}
        if resolved.api_key is not None
        else None
    )
    return TEIRerankingCapability(
        httpx.AsyncClient(base_url=str(resolved.base_url), headers=headers)
    )


def create_transcription_capability_from_environment(
    *,
    provider: ProviderSettings | None = None,
) -> TranscriptionCapability | None:
    """Create the configured OpenAI audio-transcription capability."""
    resolved_provider = provider or ProviderSettings()
    api_key = _resolve_api_key(resolved_provider)
    if api_key is None:
        return None
    base_url = _resolve_base_url(resolved_provider)
    client = (
        AsyncOpenAI(api_key=api_key, base_url=base_url)
        if base_url is not None
        else AsyncOpenAI(api_key=api_key)
    )
    return OpenAITranscriptionCapability(client)


def create_provider_health_check_from_environment(
    *,
    provider: ProviderSettings | None = None,
    readiness: ReadinessSettings | None = None,
) -> DependencyHealthCheck | None:
    """Create an opt-in provider dependency health check.

    Args:
        provider: Optional provider configuration.
        readiness: Optional dependency readiness configuration.

    Returns:
        A configured bounded provider check, or ``None`` when dependency checks
        are disabled.
    """
    resolved_provider = provider or ProviderSettings()
    resolved_readiness = readiness or ReadinessSettings()

    if not resolved_readiness.dependency_checks_enabled:
        return None

    api_key = _resolve_api_key(resolved_provider)

    if api_key is None:
        return UnavailableDependencyHealthCheck(
            provider=resolved_provider.name,
            model=resolved_readiness.required_model,
            reason=DependencyFailureReason.PROVIDER_NOT_CONFIGURED,
        )

    base_url = _resolve_base_url(resolved_provider)
    client = (
        AsyncOpenAI(api_key=api_key, base_url=base_url)
        if base_url is not None
        else AsyncOpenAI(api_key=api_key)
    )
    return OpenAICompatibleProviderHealthCheck(
        client,
        provider=resolved_provider.name,
        model=resolved_readiness.required_model,
    )


def _resolve_api_key(provider: ProviderSettings) -> str | None:
    """Resolve an SDK credential while preserving legacy OpenAI settings."""
    if provider.api_key is not None:
        value = provider.api_key.get_secret_value().strip()

        if value:
            return value

    if provider.name is ProviderName.OLLAMA:
        return OLLAMA_DEFAULT_API_KEY

    legacy_value = os.getenv("OPENAI_API_KEY", "").strip()
    return legacy_value or None


def _resolve_base_url(provider: ProviderSettings) -> str | None:
    """Resolve an OpenAI-compatible API URL for the configured provider."""
    if provider.base_url is not None:
        return str(provider.base_url).rstrip("/")

    if provider.name is ProviderName.OLLAMA:
        return OLLAMA_DEFAULT_BASE_URL

    legacy_value = os.getenv("OPENAI_BASE_URL", "").strip()
    return legacy_value.rstrip("/") or None
