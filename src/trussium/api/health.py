"""Health check API endpoints."""

from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


class HealthResponse(BaseModel):
    """Response returned by runtime health endpoints."""

    status: Literal["ok"] = "ok"


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
    "/ready",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check runtime readiness",
)
async def check_readiness() -> HealthResponse:
    """Confirm that the Trussium runtime can receive requests."""
    return HealthResponse()
