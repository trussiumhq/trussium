"""Application configuration."""

import re
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
    model_validator,
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


class RerankingSettings(BaseModel):
    """Dedicated privately hosted reranking provider configuration."""

    model_config = ConfigDict(frozen=True)

    base_url: AnyHttpUrl | None = Field(
        default=None,
        description="Optional Hugging Face Text Embeddings Inference base URL.",
    )
    api_key: SecretStr | None = Field(default=None, description="Optional TEI credential.")


class RoutingSettings(BaseModel):
    """Deterministic provider selection configuration."""

    model_config = ConfigDict(frozen=True)

    provider_priority: tuple[str, ...] = Field(
        default=(),
        description="Ordered provider names to prefer during capability selection.",
    )

    model_fallbacks: dict[str, tuple[str, ...]] = Field(
        default_factory=dict,
        description="Ordered fallback model IDs keyed by the requested model name.",
    )

    circuit_breaker_failure_threshold: int = Field(default=5, ge=1, le=100)
    circuit_breaker_reset_seconds: FiniteFloat = Field(default=30.0, gt=0.0)

    @model_validator(mode="after")
    def validate_model_fallbacks(self) -> "RoutingSettings":
        pattern = re.compile(r"[a-z][a-z0-9_.:-]{0,63}")
        if len(self.model_fallbacks) > 64:
            raise ValueError("At most 64 model fallback policies may be configured")
        for name, models in self.model_fallbacks.items():
            if pattern.fullmatch(name) is None or not models or len(models) > 10:
                raise ValueError("Model fallback names and lists must be bounded")
            if any(
                not model.strip() or len(model) > 128 or model != model.strip() for model in models
            ):
                raise ValueError("Model fallback IDs must be non-empty and stripped")
            if len(set(models)) != len(models):
                raise ValueError("Model fallback IDs must be unique")
        return self


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

    capability_health_timeout_seconds: FiniteFloat = Field(
        default=1.0,
        gt=0.0,
        description="Maximum duration of one capability health check.",
    )

    model_discovery_timeout_seconds: FiniteFloat = Field(
        default=1.0,
        gt=0.0,
        description="Maximum duration of one provider model discovery request.",
    )

    idempotency_ttl_seconds: FiniteFloat = Field(default=300.0, gt=0.0)
    idempotency_max_entries: int = Field(default=1024, ge=1, le=100_000)

    model_aliases: dict[str, str] = Field(
        default_factory=dict,
        description="Optional bounded client model aliases mapped to provider model IDs.",
    )

    @model_validator(mode="after")
    def validate_model_aliases(self) -> "RuntimeSettings":
        """Validate aliases without exposing or accepting ambiguous mappings."""
        if len(self.model_aliases) > 64:
            raise ValueError("At most 64 model aliases may be configured")
        pattern = re.compile(r"[a-z][a-z0-9_.:-]{0,63}")
        for alias, target in self.model_aliases.items():
            if pattern.fullmatch(alias) is None:
                raise ValueError("Model aliases must use bounded lowercase names")
            if not isinstance(target, str) or not target.strip() or len(target) > 128:
                raise ValueError("Model alias targets must be non-empty and at most 128 characters")
            if target != target.strip() or any(ord(character) < 32 for character in target):
                raise ValueError("Model alias targets must be stripped and contain no controls")
        return self


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


class RetrySettings(BaseModel):
    """Bounded provider retry configuration."""

    model_config = ConfigDict(frozen=True)

    max_attempts: int = Field(default=1, ge=1, le=10)
    base_delay_seconds: FiniteFloat = Field(default=0.25, ge=0.0)
    max_delay_seconds: FiniteFloat = Field(default=10.0, ge=0.0)

    @model_validator(mode="after")
    def validate_delays(self) -> "RetrySettings":
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("Retry maximum delay must be at least the base delay")
        return self


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
    reranking: RerankingSettings = RerankingSettings()
    routing: RoutingSettings = RoutingSettings()
    timeouts: TimeoutSettings = TimeoutSettings()
    retries: RetrySettings = RetrySettings()
    readiness: ReadinessSettings = ReadinessSettings()
    observability: ObservabilitySettings = ObservabilitySettings()


def resolve_model_alias(model: str, aliases: dict[str, str]) -> str:
    """Resolve one client-facing model name through a bounded alias map."""
    return aliases.get(model, model)


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()
