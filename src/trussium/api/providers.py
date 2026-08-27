"""Bounded provider and model discovery API."""

import asyncio
from typing import cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from trussium.providers import (
    ProviderModel,
    ProviderModelDiscovery,
    ProviderRegistry,
    validate_provider_name,
)

router = APIRouter(prefix="/v1/providers", tags=["providers"])


class ProviderMetadataResponse(BaseModel):
    """Bounded public metadata for one configured provider."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    capabilities: list[str] = Field(default_factory=list)
    description: str | None = None


class ProviderDiscoveryResponse(BaseModel):
    """Ordered public discovery response for configured providers."""

    model_config = ConfigDict(frozen=True)

    providers: list[ProviderMetadataResponse] = Field(default_factory=list)


class ProviderModelResponse(BaseModel):
    """Bounded public metadata for one provider model."""

    model_config = ConfigDict(frozen=True)

    id: str
    owned_by: str | None = None


class ProviderModelDiscoveryResponse(BaseModel):
    """Bounded model discovery result for one provider."""

    model_config = ConfigDict(frozen=True)

    provider: str
    status: str
    models: list[ProviderModelResponse] = Field(default_factory=list)
    reason: str | None = None


@router.get(
    "",
    response_model=ProviderDiscoveryResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Discover configured providers",
)
async def discover_providers(request: Request) -> ProviderDiscoveryResponse:
    """Return bounded metadata without executing or probing providers."""
    registry = cast(
        ProviderRegistry | None,
        getattr(request.app.state, "provider_registry", None),
    )
    if registry is None:
        return ProviderDiscoveryResponse()

    return ProviderDiscoveryResponse(
        providers=[
            ProviderMetadataResponse(
                name=metadata.name,
                version=metadata.version,
                capabilities=list(metadata.capabilities),
                description=metadata.description,
            )
            for metadata in registry.metadata
        ]
    )


@router.get(
    "/{provider_name}/models",
    response_model=ProviderModelDiscoveryResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Discover provider models",
)
async def discover_provider_models(
    provider_name: str,
    request: Request,
) -> ProviderModelDiscoveryResponse:
    """Return bounded model metadata without executing inference."""
    provider_name = validate_provider_name(provider_name)
    registry = cast(ProviderRegistry | None, getattr(request.app.state, "provider_registry", None))
    provider = registry.get(provider_name) if registry is not None else None
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "provider_not_found", "message": "Provider is not registered."},
        )
    if not isinstance(provider, ProviderModelDiscovery):
        return ProviderModelDiscoveryResponse(
            provider=provider_name,
            status="unavailable",
            reason="model_discovery_not_supported",
        )

    settings = getattr(request.app.state, "settings", None)
    timeout_seconds = getattr(
        getattr(settings, "runtime", None), "model_discovery_timeout_seconds", 1.0
    )
    try:
        async with asyncio.timeout(timeout_seconds):
            models = tuple(await provider.list_models())
        if len(models) > 256 or any(not isinstance(model, ProviderModel) for model in models):
            raise ValueError("invalid model response")
        if len({model.id for model in models}) != len(models):
            raise ValueError("duplicate model response")
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        return ProviderModelDiscoveryResponse(
            provider=provider_name, status="unavailable", reason="model_discovery_timeout"
        )
    except Exception:
        return ProviderModelDiscoveryResponse(
            provider=provider_name, status="unavailable", reason="model_discovery_failed"
        )

    return ProviderModelDiscoveryResponse(
        provider=provider_name,
        status="available",
        models=[ProviderModelResponse(id=model.id, owned_by=model.owned_by) for model in models],
    )


__all__ = [
    "ProviderDiscoveryResponse",
    "ProviderMetadataResponse",
    "ProviderModelDiscoveryResponse",
    "ProviderModelResponse",
    "discover_provider_models",
    "discover_providers",
    "router",
]
