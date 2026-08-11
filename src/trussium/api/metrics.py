"""Prometheus-compatible runtime metrics endpoint."""

from typing import cast

from fastapi import APIRouter, Request, Response

from trussium.observability import METRICS_CONTENT_TYPE, RuntimeMetrics

router = APIRouter(tags=["observability"])


@router.get(
    "/metrics",
    include_in_schema=False,
    summary="Export runtime metrics",
)
async def export_metrics(request: Request) -> Response:
    """Return the application-scoped Prometheus metric registry."""
    metrics = cast(RuntimeMetrics, request.app.state.runtime_metrics)
    return Response(
        content=metrics.render(),
        headers={"Content-Type": METRICS_CONTENT_TYPE},
    )
