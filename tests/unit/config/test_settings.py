import pytest
from pydantic import ValidationError

from trussium.config.settings import Environment, Settings


def test_default_settings() -> None:
    settings = Settings()

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.runtime.host == "0.0.0.0"
    assert settings.runtime.port == 9000
    assert settings.runtime.debug is False
    assert settings.timeouts.provider_request_seconds == 60.0
    assert settings.timeouts.stream_idle_seconds == 30.0


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
