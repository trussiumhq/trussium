"""Bounded provider discovery API."""

from typing import cast

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field

from trussium.providers import ProviderRegistry

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


__all__ = [
    "ProviderDiscoveryResponse",
    "ProviderMetadataResponse",
    "discover_providers",
    "router",
]
