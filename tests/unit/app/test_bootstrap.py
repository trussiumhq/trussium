"""Tests for runtime dependency bootstrap."""

import asyncio

import pytest
from pydantic import AnyHttpUrl, SecretStr

from trussium.app.bootstrap import (
    OLLAMA_DEFAULT_API_KEY,
    OLLAMA_DEFAULT_BASE_URL,
    create_chat_capability_from_environment,
    create_provider_health_check_from_environment,
)
from trussium.config import ProviderName, ProviderSettings, ReadinessSettings
from trussium.observability import LoggingProviderChatCapability
from trussium.providers.ollama import OllamaChatCapability
from trussium.providers.openai import OpenAIChatCapability, OpenAICompatibleProviderHealthCheck
from trussium.runtime import (
    DependencyFailureReason,
    TimeoutChatCapability,
    UnavailableDependencyHealthCheck,
)


def test_missing_openai_api_key_disables_chat_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime should start without an OpenAI API key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    capability = create_chat_capability_from_environment()

    assert capability is None


def test_dependency_checks_are_disabled_without_creating_provider_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward-compatible defaults should never create a network check."""
    monkeypatch.setenv("OPENAI_API_KEY", "unused-key")

    check = create_provider_health_check_from_environment()

    assert check is None


def test_enabled_check_reports_missing_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit dependency gating should fail closed without a credential."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    readiness = ReadinessSettings(
        dependency_checks_enabled=True,
        required_model="required-model",
    )

    check = create_provider_health_check_from_environment(readiness=readiness)

    assert isinstance(check, UnavailableDependencyHealthCheck)
    result = asyncio.run(check.check())
    assert result.reason is DependencyFailureReason.PROVIDER_NOT_CONFIGURED
    assert result.model == "required-model"


def test_enabled_openai_check_uses_typed_provider_configuration() -> None:
    """Readiness should construct an independent metadata-only SDK client."""
    provider = ProviderSettings(
        name=ProviderName.OPENAI,
        base_url=AnyHttpUrl("https://provider.example/v1"),
        api_key=SecretStr("health-key"),
    )
    readiness = ReadinessSettings(
        dependency_checks_enabled=True,
        required_model="required-model",
    )

    check = create_provider_health_check_from_environment(
        provider=provider,
        readiness=readiness,
    )

    assert isinstance(check, OpenAICompatibleProviderHealthCheck)
    assert check.provider == "openai"
    assert check.model == "required-model"
    assert check._client.api_key == "health-key"
    assert str(check._client.base_url) == "https://provider.example/v1/"
    asyncio.run(check.close())


def test_enabled_ollama_check_uses_local_compatible_defaults() -> None:
    """Ollama should share the metadata check without external credentials."""
    check = create_provider_health_check_from_environment(
        provider=ProviderSettings(name=ProviderName.OLLAMA),
        readiness=ReadinessSettings(dependency_checks_enabled=True),
    )

    assert isinstance(check, OpenAICompatibleProviderHealthCheck)
    assert check.provider == "ollama"
    assert check.model is None
    assert check._client.api_key == OLLAMA_DEFAULT_API_KEY
    assert str(check._client.base_url) == f"{OLLAMA_DEFAULT_BASE_URL}/"
    asyncio.run(check.close())


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
