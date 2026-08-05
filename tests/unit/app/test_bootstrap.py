"""Tests for runtime dependency bootstrap."""

import pytest
from pydantic import AnyHttpUrl, SecretStr

from trussium.app.bootstrap import (
    OLLAMA_DEFAULT_API_KEY,
    OLLAMA_DEFAULT_BASE_URL,
    create_chat_capability_from_environment,
)
from trussium.config import ProviderName, ProviderSettings
from trussium.observability import LoggingProviderChatCapability
from trussium.providers.ollama import OllamaChatCapability
from trussium.providers.openai import OpenAIChatCapability
from trussium.runtime import TimeoutChatCapability


def test_missing_openai_api_key_disables_chat_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime should start without an OpenAI API key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    capability = create_chat_capability_from_environment()

    assert capability is None


def test_openai_api_key_enables_logged_openai_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An OpenAI API key should enable the OpenAI adapter."""
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-api-key",
    )

    capability = create_chat_capability_from_environment()

    assert isinstance(
        capability,
        LoggingProviderChatCapability,
    )
    assert isinstance(
        capability._capability,
        TimeoutChatCapability,
    )
    assert isinstance(capability._capability._capability, OpenAIChatCapability)
    assert capability._provider == "openai"


def test_legacy_openai_base_url_configures_sdk_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing OpenAI SDK environment configuration should remain valid."""
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-api-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://legacy-openai.test/v1/")

    capability = create_chat_capability_from_environment()

    assert isinstance(capability, LoggingProviderChatCapability)
    timeout_capability = capability._capability
    assert isinstance(timeout_capability, TimeoutChatCapability)
    adapter = timeout_capability._capability
    assert isinstance(adapter, OpenAIChatCapability)
    assert str(adapter._client.base_url) == "http://legacy-openai.test/v1/"


def test_typed_openai_settings_take_precedence_over_legacy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit Trussium provider settings should override legacy values."""
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-api-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://legacy-openai.test/v1")
    provider = ProviderSettings(
        name=ProviderName.OPENAI,
        base_url=AnyHttpUrl("http://configured-openai.test/v1"),
        api_key=SecretStr("configured-api-key"),
    )

    capability = create_chat_capability_from_environment(provider=provider)

    assert isinstance(capability, LoggingProviderChatCapability)
    timeout_capability = capability._capability
    assert isinstance(timeout_capability, TimeoutChatCapability)
    adapter = timeout_capability._capability
    assert isinstance(adapter, OpenAIChatCapability)
    assert adapter._client.api_key == "configured-api-key"
    assert str(adapter._client.base_url) == "http://configured-openai.test/v1/"


def test_ollama_settings_enable_provider_without_external_credential() -> None:
    """Ollama should use its local defaults and provider identity."""
    capability = create_chat_capability_from_environment(
        provider=ProviderSettings(name=ProviderName.OLLAMA)
    )

    assert isinstance(capability, LoggingProviderChatCapability)
    assert capability._provider == "ollama"
    timeout_capability = capability._capability
    assert isinstance(timeout_capability, TimeoutChatCapability)
    adapter = timeout_capability._capability
    assert isinstance(adapter, OllamaChatCapability)
    assert adapter._client.api_key == OLLAMA_DEFAULT_API_KEY
    assert str(adapter._client.base_url) == f"{OLLAMA_DEFAULT_BASE_URL}/"


def test_ollama_settings_support_remote_compatible_endpoint() -> None:
    """Ollama-compatible endpoints should accept explicit URL and credential."""
    provider = ProviderSettings(
        name=ProviderName.OLLAMA,
        base_url=AnyHttpUrl("https://ollama.internal.example/v1"),
        api_key=SecretStr("gateway-key"),
    )

    capability = create_chat_capability_from_environment(provider=provider)

    assert isinstance(capability, LoggingProviderChatCapability)
    timeout_capability = capability._capability
    assert isinstance(timeout_capability, TimeoutChatCapability)
    adapter = timeout_capability._capability
    assert isinstance(adapter, OllamaChatCapability)
    assert adapter._client.api_key == "gateway-key"
    assert str(adapter._client.base_url) == "https://ollama.internal.example/v1/"
