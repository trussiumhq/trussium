"""Tests for the Prometheus-compatible runtime metrics endpoint."""

from collections.abc import AsyncIterator

from fastapi import status
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.config.settings import ObservabilitySettings, Settings
from trussium.observability import METRICS_CONTENT_TYPE, RuntimeMetrics


def test_metrics_endpoint_exposes_runtime_registry() -> None:
    client = TestClient(create_application())

    missing = client.get("/workload-not-found")
    response = client.get("/metrics")

    assert missing.status_code == status.HTTP_404_NOT_FOUND
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == METRICS_CONTENT_TYPE
    assert "python_info" in response.text
    assert "trussium_http_requests_active 0.0" in response.text
    assert (
        'trussium_http_requests_total{method="GET",outcome="completed",status_code="404"} 1.0'
        in response.text
    )


def test_operational_endpoints_do_not_change_workload_metrics() -> None:
    client = TestClient(create_application())

    assert client.get("/health/live").status_code == status.HTTP_200_OK
    assert client.get("/health/ready").status_code == status.HTTP_200_OK
    assert client.get("/health/components").status_code == status.HTTP_200_OK
    metrics = client.get("/metrics").text

    assert "trussium_http_requests_total{" not in metrics
    assert "trussium_http_request_duration_seconds_count{" not in metrics


def test_metrics_track_stream_until_terminal_body() -> None:
    application = create_application()
    metrics = application.state.runtime_metrics
    assert isinstance(metrics, RuntimeMetrics)

    @application.get("/metric-stream")
    async def metric_stream() -> StreamingResponse:
        async def generate() -> AsyncIterator[str]:
            yield metrics.render().decode()

        return StreamingResponse(generate(), media_type="text/plain")

    client = TestClient(application)

    with client.stream("GET", "/metric-stream") as response:
        body = "".join(response.iter_text())

    assert "trussium_http_requests_active 1.0" in body
    assert "trussium_http_requests_active 0.0" in client.get("/metrics").text


def test_metrics_can_be_disabled() -> None:
    settings = Settings(
        observability=ObservabilitySettings(metrics_enabled=False),
    )
    application = create_application(settings)
    client = TestClient(application)

    response = client.get("/metrics")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not hasattr(application.state, "runtime_metrics")
