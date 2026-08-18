"""Provider-neutral capability discovery API."""

from typing import cast

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field

from trussium.capabilities import CapabilityRegistry

router = APIRouter(
    prefix="/v1/capabilities",
    tags=["capabilities"],
)


class CapabilityMetadataResponse(BaseModel):
    """Bounded public metadata for one configured capability contract."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str | None = None
    description: str | None = None
    supports_streaming: bool | None = None


class CapabilityDiscoveryResponse(BaseModel):
    """Ordered public discovery response for configured capabilities."""

    model_config = ConfigDict(frozen=True)

    capabilities: list[CapabilityMetadataResponse] = Field(default_factory=list)


@router.get(
    "",
    response_model=CapabilityDiscoveryResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Discover configured capabilities",
)
async def discover_capabilities(request: Request) -> CapabilityDiscoveryResponse:
    """Return bounded metadata without executing or probing capabilities."""
    registry = cast(
        CapabilityRegistry | None,
        getattr(request.app.state, "capability_registry", None),
    )
    if registry is None:
        return CapabilityDiscoveryResponse()

    return CapabilityDiscoveryResponse(
        capabilities=[
            CapabilityMetadataResponse(
                name=metadata.name,
                version=metadata.version,
                description=metadata.description,
                supports_streaming=metadata.supports_streaming,
            )
            for metadata in registry.metadata
        ]
    )


__all__ = [
    "CapabilityDiscoveryResponse",
    "CapabilityMetadataResponse",
    "discover_capabilities",
    "router",
]
