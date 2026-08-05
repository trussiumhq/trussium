"""Application configuration."""

from enum import StrEnum
from functools import lru_cache

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()
