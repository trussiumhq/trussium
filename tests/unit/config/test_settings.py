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
    assert settings.runtime.service_cleanup_seconds == 10.0
    assert settings.runtime.component_health_timeout_seconds == 1.0
    assert settings.runtime.capability_availability_timeout_seconds == 1.0
    assert settings.runtime.capability_health_timeout_seconds == 1.0
    assert settings.runtime.model_aliases == {}
    assert settings.provider.name is ProviderName.OPENAI
    assert settings.provider.base_url is None
    assert settings.provider.api_key is None
    assert settings.authentication.api_keys == ()
    assert settings.authentication.identity_bindings == ()
    assert settings.timeouts.provider_request_seconds == 60.0
    assert settings.timeouts.stream_idle_seconds == 30.0
    assert settings.readiness.dependency_checks_enabled is False
    assert settings.readiness.dependency_timeout_seconds == 1.0
    assert settings.readiness.dependency_cache_seconds == 10.0
    assert settings.readiness.required_model is None
    assert settings.observability.metrics_enabled is True
    assert settings.observability.tracing_enabled is False
    assert settings.observability.tracing_service_name == "trussium"
    assert settings.observability.tracing_sample_ratio == 1.0
    assert str(settings.observability.otlp_traces_endpoint) == "http://127.0.0.1:4318/v1/traces"
    assert settings.observability.otlp_export_timeout_seconds == 10.0


def test_authentication_settings_support_bounded_secret_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSSIUM_AUTHENTICATION__API_KEYS", '["key-one", "key-two"]')
    settings = Settings()
    assert [key.get_secret_value() for key in settings.authentication.api_keys] == [
        "key-one",
        "key-two",
    ]


def test_authentication_settings_reject_duplicate_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSSIUM_AUTHENTICATION__API_KEYS", '["same", "same"]')
    with pytest.raises(ValidationError):
        Settings()


def test_authentication_settings_load_identity_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TRUSSIUM_AUTHENTICATION__IDENTITY_BINDINGS",
        '[{"key":"bound-key","tenant_id":"tenant-1","project_id":"project-1","capabilities":["chat"]}]',
    )
    settings = Settings()
    binding = settings.authentication.identity_bindings[0]
    assert binding.key.get_secret_value() == "bound-key"
    assert binding.tenant_id == "tenant-1"
    assert binding.project_id == "project-1"
    assert binding.capabilities == ("chat",)


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


def test_model_aliases_support_typed_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model aliases should be bounded and loaded from nested runtime settings."""
    monkeypatch.setenv(
        "TRUSSIUM_RUNTIME__MODEL_ALIASES",
        '{"fast":"provider-model-v2"}',
    )

    settings = Settings()

    assert settings.runtime.model_aliases == {"fast": "provider-model-v2"}


@pytest.mark.parametrize(
    "value",
    ['{"Fast":"model"}', '{"fast":"   "}', '{"fast":"model\\n"}'],
)
def test_model_aliases_reject_invalid_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Unsafe aliases should fail before runtime startup."""
    monkeypatch.setenv("TRUSSIUM_RUNTIME__MODEL_ALIASES", value)

    with pytest.raises(ValidationError):
        Settings()


def test_readiness_settings_support_typed_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dependency readiness settings should be typed and immutable."""
    monkeypatch.setenv("TRUSSIUM_READINESS__DEPENDENCY_CHECKS_ENABLED", "true")
    monkeypatch.setenv("TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS", "0.75")
    monkeypatch.setenv("TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS", "3.5")
    monkeypatch.setenv("TRUSSIUM_READINESS__REQUIRED_MODEL", "  required-model  ")

    settings = Settings()

    assert settings.readiness.dependency_checks_enabled is True
    assert settings.readiness.dependency_timeout_seconds == 0.75
    assert settings.readiness.dependency_cache_seconds == 3.5
    assert settings.readiness.required_model == "required-model"

    with pytest.raises(ValidationError):
        settings.readiness.required_model = "other-model"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS", "0"),
        ("TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS", "-1"),
        ("TRUSSIUM_READINESS__REQUIRED_MODEL", "   "),
    ],
)
def test_readiness_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    """Unsafe readiness values should fail before process startup."""
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()


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


def test_runtime_service_cleanup_settings_are_typed_and_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime-service cleanup should have a positive environment deadline."""
    monkeypatch.setenv(
        "TRUSSIUM_RUNTIME__SERVICE_CLEANUP_SECONDS",
        "2.5",
    )

    settings = Settings()

    assert settings.runtime.service_cleanup_seconds == 2.5

    with pytest.raises(ValidationError):
        settings.runtime.service_cleanup_seconds = 1.0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_runtime_service_cleanup_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Invalid cleanup deadlines should fail before runtime startup."""
    monkeypatch.setenv("TRUSSIUM_RUNTIME__SERVICE_CLEANUP_SECONDS", value)

    with pytest.raises(ValidationError):
        Settings()


def test_runtime_component_health_timeout_is_typed_and_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Component health checks should have a positive environment deadline."""
    monkeypatch.setenv(
        "TRUSSIUM_RUNTIME__COMPONENT_HEALTH_TIMEOUT_SECONDS",
        "0.75",
    )

    settings = Settings()

    assert settings.runtime.component_health_timeout_seconds == 0.75

    with pytest.raises(ValidationError):
        settings.runtime.component_health_timeout_seconds = 1.0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_runtime_component_health_timeout_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Invalid component health deadlines should fail before startup."""
    monkeypatch.setenv("TRUSSIUM_RUNTIME__COMPONENT_HEALTH_TIMEOUT_SECONDS", value)

    with pytest.raises(ValidationError):
        Settings()


def test_capability_availability_timeout_is_typed_and_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capability availability checks should have a positive environment deadline."""
    monkeypatch.setenv(
        "TRUSSIUM_RUNTIME__CAPABILITY_AVAILABILITY_TIMEOUT_SECONDS",
        "0.625",
    )

    settings = Settings()

    assert settings.runtime.capability_availability_timeout_seconds == 0.625

    with pytest.raises(ValidationError):
        settings.runtime.capability_availability_timeout_seconds = 1.0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_capability_availability_timeout_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Invalid availability deadlines should fail before startup."""
    monkeypatch.setenv("TRUSSIUM_RUNTIME__CAPABILITY_AVAILABILITY_TIMEOUT_SECONDS", value)

    with pytest.raises(ValidationError):
        Settings()


def test_capability_health_timeout_is_typed_and_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capability health checks should have a positive environment deadline."""
    monkeypatch.setenv("TRUSSIUM_RUNTIME__CAPABILITY_HEALTH_TIMEOUT_SECONDS", "0.625")
    settings = Settings()
    assert settings.runtime.capability_health_timeout_seconds == 0.625
    with pytest.raises(ValidationError):
        settings.runtime.capability_health_timeout_seconds = 1.0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_capability_health_timeout_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Invalid capability-health deadlines should fail before startup."""
    monkeypatch.setenv("TRUSSIUM_RUNTIME__CAPABILITY_HEALTH_TIMEOUT_SECONDS", value)
    with pytest.raises(ValidationError):
        Settings()


def test_observability_settings_support_metrics_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metrics exposure should use typed immutable nested settings."""
    monkeypatch.setenv("TRUSSIUM_OBSERVABILITY__METRICS_ENABLED", "false")

    settings = Settings()

    assert settings.observability.metrics_enabled is False

    with pytest.raises(ValidationError):
        settings.observability.metrics_enabled = True


def test_observability_settings_support_tracing_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tracing should use typed immutable nested settings."""
    monkeypatch.setenv("TRUSSIUM_OBSERVABILITY__TRACING_ENABLED", "true")
    monkeypatch.setenv(
        "TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME",
        "  trussium-edge  ",
    )
    monkeypatch.setenv("TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO", "0.25")
    monkeypatch.setenv(
        "TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT",
        "https://collector.example/v1/traces",
    )
    monkeypatch.setenv(
        "TRUSSIUM_OBSERVABILITY__OTLP_EXPORT_TIMEOUT_SECONDS",
        "2.5",
    )

    settings = Settings()

    assert settings.observability.tracing_enabled is True
    assert settings.observability.tracing_service_name == "trussium-edge"
    assert settings.observability.tracing_sample_ratio == 0.25
    assert str(settings.observability.otlp_traces_endpoint) == "https://collector.example/v1/traces"
    assert settings.observability.otlp_export_timeout_seconds == 2.5

    with pytest.raises(ValidationError):
        settings.observability.tracing_enabled = False


@pytest.mark.parametrize(
    ("environment_name", "value"),
    [
        ("TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME", "   "),
        ("TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO", "-0.1"),
        ("TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO", "1.1"),
        ("TRUSSIUM_OBSERVABILITY__OTLP_EXPORT_TIMEOUT_SECONDS", "0"),
        ("TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT", "grpc://collector:4317"),
    ],
)
def test_observability_settings_reject_invalid_tracing_values(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    value: str,
) -> None:
    """Invalid tracing configuration should fail before runtime startup."""
    monkeypatch.setenv(environment_name, value)

    with pytest.raises(ValidationError):
        Settings()


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
