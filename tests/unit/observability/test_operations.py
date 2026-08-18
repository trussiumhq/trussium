"""Tests for bounded structured operational logging."""

import io
import json

from trussium import __version__
from trussium.config.settings import (
    Environment,
    ObservabilitySettings,
    ProviderName,
    ProviderSettings,
    RuntimeSettings,
    Settings,
)
from trussium.observability import configure_logging, log_startup_configuration


def _payloads(output: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.getvalue().splitlines()]


def test_startup_configuration_logs_safe_bounded_summaries() -> None:
    """Startup summaries should expose useful fields without sensitive settings."""
    output = io.StringIO()
    configure_logging(stream=output)
    settings = Settings.model_validate(
        {
            "environment": Environment.PRODUCTION,
            "runtime": RuntimeSettings(
                port=9042,
                graceful_shutdown_seconds=17,
                service_cleanup_seconds=3.5,
            ),
            "provider": ProviderSettings.model_validate(
                {
                    "name": ProviderName.OPENAI,
                    "api_key": "secret-provider-key",
                    "base_url": "https://secret-provider.example/v1",
                }
            ),
            "observability": ObservabilitySettings.model_validate(
                {
                    "metrics_enabled": False,
                    "tracing_enabled": True,
                    "tracing_service_name": "secret-service-name",
                    "tracing_sample_ratio": 0.25,
                    "otlp_traces_endpoint": "https://secret-collector.example/v1/traces",
                }
            ),
        }
    )

    log_startup_configuration(settings, provider_configured=True)

    payloads = _payloads(output)
    by_event = {str(payload["event"]): payload for payload in payloads}

    assert set(by_event) == {
        "runtime.configuration.loaded",
        "provider.configuration.ready",
        "readiness.configuration.loaded",
        "observability.configuration.loaded",
    }
    runtime_payload = by_event["runtime.configuration.loaded"]
    assert runtime_payload["level"] == "INFO"
    assert runtime_payload["logger"] == "trussium.runtime"
    assert runtime_payload["message"] == "Runtime configuration loaded"
    assert runtime_payload["runtime_version"] == __version__
    assert runtime_payload["environment"] == "production"
    assert runtime_payload["port"] == 9042
    assert runtime_payload["debug"] is False
    assert runtime_payload["graceful_shutdown_seconds"] == 17
    assert runtime_payload["service_cleanup_seconds"] == 3.5
    assert "duration_ms" not in runtime_payload
    assert by_event["provider.configuration.ready"]["provider"] == "openai"
    assert by_event["provider.configuration.ready"]["logger"] == "trussium.provider"
    assert by_event["provider.configuration.ready"]["provider_configured"] is True
    readiness_payload = by_event["readiness.configuration.loaded"]
    assert readiness_payload["logger"] == "trussium.readiness"
    assert readiness_payload["dependency_checks_enabled"] is False
    assert readiness_payload["dependency_timeout_seconds"] == 1.0
    assert readiness_payload["dependency_cache_seconds"] == 10.0
    assert readiness_payload["required_model_configured"] is False
    assert by_event["observability.configuration.loaded"]["metrics_enabled"] is False
    assert by_event["observability.configuration.loaded"]["logger"] == "trussium.observability"
    assert by_event["observability.configuration.loaded"]["tracing_enabled"] is True
    assert by_event["observability.configuration.loaded"]["trace_sample_ratio"] == 0.25

    serialized = output.getvalue()
    assert "secret-provider-key" not in serialized
    assert "secret-provider.example" not in serialized
    assert "secret-service-name" not in serialized
    assert "secret-collector.example" not in serialized


def test_missing_provider_configuration_emits_warning() -> None:
    """Missing provider configuration should remain a non-fatal warning."""
    output = io.StringIO()
    configure_logging(stream=output)

    log_startup_configuration(Settings(), provider_configured=False)

    provider_payload = next(
        payload
        for payload in _payloads(output)
        if payload["event"] == "provider.configuration.unavailable"
    )
    assert provider_payload["level"] == "WARNING"
    assert provider_payload["provider"] == "openai"
    assert provider_payload["provider_configured"] is False


def test_default_ollama_configuration_logs_ready_without_endpoint_fields() -> None:
    """Ollama defaults should be ready without disclosing SDK configuration."""
    output = io.StringIO()
    configure_logging(stream=output)
    settings = Settings(
        provider=ProviderSettings(name=ProviderName.OLLAMA),
    )

    log_startup_configuration(settings, provider_configured=True)

    provider_payload = next(
        payload
        for payload in _payloads(output)
        if payload["event"] == "provider.configuration.ready"
    )
    assert provider_payload["provider"] == "ollama"
    assert provider_payload["provider_configured"] is True
    assert "api_key" not in provider_payload
    assert "base_url" not in provider_payload
    assert "127.0.0.1:11434" not in output.getvalue()
