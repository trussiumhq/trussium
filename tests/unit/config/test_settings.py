import pytest
from pydantic import ValidationError

from trussium.config.settings import Environment, ProviderName, Settings


def test_default_settings() -> None:
    settings = Settings()

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.runtime.host == "0.0.0.0"
    assert settings.runtime.port == 9000
    assert settings.runtime.debug is False
    assert settings.runtime.graceful_shutdown_seconds == 30
    assert settings.provider.name is ProviderName.OPENAI
    assert settings.provider.base_url is None
    assert settings.provider.api_key is None
    assert settings.timeouts.provider_request_seconds == 60.0
    assert settings.timeouts.stream_idle_seconds == 30.0
    assert settings.observability.metrics_enabled is True


def test_timeout_settings_support_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested timeout settings should use the established environment prefix."""
    monkeypatch.setenv(
        "TRUSSIUM_TIMEOUTS__PROVIDER_REQUEST_SECONDS",
        "12.5",
    )
    monkeypatch.setenv(
        "TRUSSIUM_TIMEOUTS__STREAM_IDLE_SECONDS",
        "4.25",
    )

    settings = Settings()

    assert settings.timeouts.provider_request_seconds == 12.5
    assert settings.timeouts.stream_idle_seconds == 4.25


def test_runtime_settings_support_graceful_shutdown_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The server drain deadline should use typed nested runtime settings."""
    monkeypatch.setenv(
        "TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS",
        "12",
    )

    settings = Settings()

    assert settings.runtime.graceful_shutdown_seconds == 12

    with pytest.raises(ValidationError):
        settings.runtime.graceful_shutdown_seconds = 4


def test_observability_settings_support_metrics_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metrics exposure should use typed immutable nested settings."""
    monkeypatch.setenv("TRUSSIUM_OBSERVABILITY__METRICS_ENABLED", "false")

    settings = Settings()

    assert settings.observability.metrics_enabled is False

    with pytest.raises(ValidationError):
        settings.observability.metrics_enabled = True


def test_provider_settings_support_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested provider settings should use typed immutable values."""
    monkeypatch.setenv("TRUSSIUM_PROVIDER__NAME", "ollama")
    monkeypatch.setenv(
        "TRUSSIUM_PROVIDER__BASE_URL",
        "http://ollama.internal:11434/v1",
    )
    monkeypatch.setenv("TRUSSIUM_PROVIDER__API_KEY", "private-provider-key")

    settings = Settings()

    assert settings.provider.name is ProviderName.OLLAMA
    assert str(settings.provider.base_url) == "http://ollama.internal:11434/v1"
    assert settings.provider.api_key is not None
    assert settings.provider.api_key.get_secret_value() == "private-provider-key"
    assert "private-provider-key" not in repr(settings.provider)

    with pytest.raises(ValidationError):
        settings.provider.name = ProviderName.OPENAI


def test_provider_settings_reject_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only providers with runtime composition should be selectable."""
    monkeypatch.setenv("TRUSSIUM_PROVIDER__NAME", "unsupported")

    with pytest.raises(ValidationError):
        Settings()


def test_provider_settings_reject_non_http_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider base URLs should use an HTTP transport."""
    monkeypatch.setenv("TRUSSIUM_PROVIDER__BASE_URL", "ftp://provider.example/v1")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "environment_name",
    [
        "TRUSSIUM_TIMEOUTS__PROVIDER_REQUEST_SECONDS",
        "TRUSSIUM_TIMEOUTS__STREAM_IDLE_SECONDS",
    ],
)
def test_timeout_settings_reject_non_positive_values(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
) -> None:
    """Invalid runtime deadlines should fail configuration validation."""
    monkeypatch.setenv(environment_name, "0")

    with pytest.raises(ValidationError):
        Settings()


def test_runtime_settings_reject_non_positive_grace_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An immediate shutdown deadline should fail configuration validation."""
    monkeypatch.setenv(
        "TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS",
        "0",
    )

    with pytest.raises(ValidationError):
        Settings()
