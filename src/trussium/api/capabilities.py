"""Provider-neutral capability discovery and availability API."""

from typing import Literal, cast

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field

from trussium.capabilities import (
    CapabilityAvailabilityReporter,
    CapabilityHealthReporter,
    CapabilityRegistry,
)

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


class CapabilityAvailabilityResponse(BaseModel):
    """Bounded public availability for one configured capability."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["available", "unavailable"]
    reason: str | None = None


class CapabilityAvailabilityReportResponse(BaseModel):
    """Informational aggregate over configured capabilities."""

    model_config = ConfigDict(frozen=True)

    status: Literal["available", "unavailable"] = "available"
    capabilities: list[CapabilityAvailabilityResponse] = Field(default_factory=list)


class CapabilityHealthResponse(BaseModel):
    """Bounded public health for one configured capability."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ok", "degraded", "unavailable", "unknown"]
    reason: str | None = None


class CapabilityHealthReportResponse(BaseModel):
    """Informational aggregate over configured capability health."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "degraded", "unavailable", "unknown"] = "ok"
    capabilities: list[CapabilityHealthResponse] = Field(default_factory=list)


@router.get(
    "/availability",
    response_model=CapabilityAvailabilityReportResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Report capability availability",
)
async def report_capability_availability(
    request: Request,
) -> CapabilityAvailabilityReportResponse:
    """Report informational availability without affecting execution or readiness."""
    reporter = cast(
        CapabilityAvailabilityReporter | None,
        getattr(request.app.state, "capability_availability_reporter", None),
    )
    if reporter is None:
        return CapabilityAvailabilityReportResponse()

    report = await reporter.report()
    return CapabilityAvailabilityReportResponse(
        status=report.status.value,
        capabilities=[
            CapabilityAvailabilityResponse(
                name=capability.name,
                status=capability.status.value,
                reason=capability.reason,
            )
            for capability in report.capabilities
        ],
    )


@router.get(
    "/health",
    response_model=CapabilityHealthReportResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Report capability health",
)
async def report_capability_health(request: Request) -> CapabilityHealthReportResponse:
    """Report informational health without affecting availability or readiness."""
    reporter = cast(
        CapabilityHealthReporter | None,
        getattr(request.app.state, "capability_health_reporter", None),
    )
    if reporter is None:
        return CapabilityHealthReportResponse()

    report = await reporter.report()
    return CapabilityHealthReportResponse(
        status=report.status.value,
        capabilities=[
            CapabilityHealthResponse(
                name=capability.name,
                status=capability.status.value,
                reason=capability.reason,
            )
            for capability in report.capabilities
        ],
    )


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
    "CapabilityAvailabilityReportResponse",
    "CapabilityAvailabilityResponse",
    "CapabilityDiscoveryResponse",
    "CapabilityHealthReportResponse",
    "CapabilityHealthResponse",
    "CapabilityMetadataResponse",
    "discover_capabilities",
    "report_capability_availability",
    "report_capability_health",
    "router",
]
