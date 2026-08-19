"""Application configuration."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    SecretStr,
    StringConstraints,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ProviderName(StrEnum):
    """Supported runtime chat providers."""

    OPENAI = "openai"
    OLLAMA = "ollama"


class ProviderSettings(BaseModel):
    """Chat provider configuration."""

    model_config = ConfigDict(frozen=True)

    name: ProviderName = Field(
        default=ProviderName.OPENAI,
        description="Active chat provider.",
    )

    base_url: AnyHttpUrl | None = Field(
        default=None,
        description="Optional OpenAI-compatible provider base URL.",
    )

    api_key: SecretStr | None = Field(
        default=None,
        description="Optional provider credential.",
    )


class RuntimeSettings(BaseModel):
    """Runtime configuration."""

    model_config = ConfigDict(frozen=True)

    host: str = Field(
        default="0.0.0.0",
        description="Host interface to bind the server.",
    )

    port: int = Field(
        default=9000,
        ge=1,
        le=65535,
        description="Port the server listens on.",
    )

    debug: bool = Field(
        default=False,
        description="Enable debug mode.",
    )

    graceful_shutdown_seconds: int = Field(
        default=30,
        gt=0,
        description=(
            "Maximum time to drain active requests before they are cancelled during shutdown."
        ),
    )

    service_cleanup_seconds: FiniteFloat = Field(
        default=10.0,
        gt=0.0,
        description="Maximum duration of one runtime-service cleanup hook.",
    )

    component_health_timeout_seconds: FiniteFloat = Field(
        default=1.0,
        gt=0.0,
        description="Maximum duration of one runtime-component health check.",
    )

    capability_availability_timeout_seconds: FiniteFloat = Field(
        default=1.0,
        gt=0.0,
        description="Maximum duration of one capability availability check.",
    )


class TimeoutSettings(BaseModel):
    """Provider execution timeout configuration."""

    model_config = ConfigDict(frozen=True)

    provider_request_seconds: float = Field(
        default=60.0,
        gt=0,
        description="Maximum duration of a non-streaming provider request.",
    )

    stream_idle_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Maximum wait between provider stream events.",
    )


class ReadinessSettings(BaseModel):
    """Dependency-aware readiness configuration."""

    model_config = ConfigDict(frozen=True)

    dependency_checks_enabled: bool = Field(
        default=False,
        description="Gate readiness on the configured provider dependency.",
    )

    dependency_timeout_seconds: float = Field(
        default=1.0,
        gt=0.0,
        description="Maximum duration of one provider readiness refresh.",
    )

    dependency_cache_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="Duration to reuse a provider readiness result.",
    )

    required_model: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1),
        ]
        | None
    ) = Field(
        default=None,
        description="Optional provider model that must be available for readiness.",
    )


class ObservabilitySettings(BaseModel):
    """Runtime observability configuration."""

    model_config = ConfigDict(frozen=True)

    metrics_enabled: bool = Field(
        default=True,
        description="Expose Prometheus-compatible runtime metrics at /metrics.",
    )

    tracing_enabled: bool = Field(
        default=False,
        description="Export OpenTelemetry runtime traces.",
    )

    tracing_service_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ] = Field(
        default="trussium",
        description="OpenTelemetry service.name resource value.",
    )

    tracing_sample_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Root trace sampling probability from zero to one.",
    )

    otlp_traces_endpoint: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://127.0.0.1:4318/v1/traces"),
        description="OTLP HTTP/protobuf traces endpoint.",
    )

    otlp_export_timeout_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="Maximum OTLP trace export request duration.",
    )


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_prefix="TRUSSIUM_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment.",
    )

    runtime: RuntimeSettings = RuntimeSettings()
    provider: ProviderSettings = ProviderSettings()
    timeouts: TimeoutSettings = TimeoutSettings()
    readiness: ReadinessSettings = ReadinessSettings()
    observability: ObservabilitySettings = ObservabilitySettings()


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()
