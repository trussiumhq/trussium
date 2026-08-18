"""Health check API endpoints."""

from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from trussium.runtime import (
    DependencyReadiness,
    DependencyStatus,
    RuntimeComponentHealthReporter,
)

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


class HealthResponse(BaseModel):
    """Response returned by runtime health endpoints."""

    status: Literal["ok"] = "ok"


class ReadinessDependencyResponse(BaseModel):
    """Bounded public state for one readiness dependency."""

    name: str
    status: Literal["ok", "unavailable"]
    provider: str
    model: str | None = None
    reason: str | None = None


class ReadinessResponse(BaseModel):
    """Response returned by the dependency-aware readiness endpoint."""

    status: Literal["ok", "unavailable"] = "ok"
    dependencies: list[ReadinessDependencyResponse] = Field(default_factory=list)


class ComponentHealthResponse(BaseModel):
    """Bounded public state for one registered runtime component."""

    name: str
    status: Literal["ok", "degraded", "unavailable", "unknown"]
    reason: str | None = None


class ComponentHealthReportResponse(BaseModel):
    """Informational aggregate over registered runtime components."""

    status: Literal["ok", "degraded", "unavailable", "unknown"] = "ok"
    components: list[ComponentHealthResponse] = Field(default_factory=list)


@router.get(
    "/live",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check runtime liveness",
)
async def check_liveness() -> HealthResponse:
    """Confirm that the Trussium runtime process is running."""
    return HealthResponse()


@router.get(
    "/components",
    response_model=ComponentHealthReportResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Report runtime component health",
)
async def check_component_health(request: Request) -> ComponentHealthReportResponse:
    """Report component states without changing liveness or readiness."""
    reporter = cast(
        RuntimeComponentHealthReporter | None,
        getattr(request.app.state, "runtime_component_health_reporter", None),
    )

    if reporter is None:
        return ComponentHealthReportResponse()

    report = await reporter.report()
    return ComponentHealthReportResponse(
        status=report.status.value,
        components=[
            ComponentHealthResponse(
                name=component.name,
                status=component.status.value,
                reason=component.reason,
            )
            for component in report.components
        ],
    )


@router.get(
    "/ready",
    response_model=HealthResponse | ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "A required runtime dependency is unavailable.",
        }
    },
    status_code=status.HTTP_200_OK,
    summary="Check runtime readiness",
)
async def check_readiness(request: Request) -> Response | HealthResponse:
    """Confirm that the runtime and enabled dependencies can receive requests."""
    readiness = cast(
        DependencyReadiness | None,
        getattr(request.app.state, "dependency_readiness", None),
    )

    if readiness is None:
        return HealthResponse()

    dependency = await readiness.evaluate()
    body = ReadinessResponse(
        status=("ok" if dependency.status is DependencyStatus.OK else "unavailable"),
        dependencies=[
            ReadinessDependencyResponse(
                name=dependency.name,
                status=dependency.status.value,
                provider=dependency.provider,
                model=dependency.model,
                reason=dependency.reason,
            )
        ],
    )
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if dependency.status is DependencyStatus.OK
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=body.model_dump(mode="json", exclude_none=True),
    )
