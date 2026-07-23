"""Application configuration."""

from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


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


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_prefix="TRUSSIUM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment.",
    )

    runtime: RuntimeSettings = RuntimeSettings()


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()
