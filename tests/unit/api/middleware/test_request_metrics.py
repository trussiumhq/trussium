"""Tests for terminal HTTP request metric outcomes."""

import asyncio
from asyncio import CancelledError
from typing import cast

import pytest
from prometheus_client.parser import text_string_to_metric_families
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from trussium.middleware import RequestMetricsMiddleware
from trussium.observability import RuntimeMetrics


def http_scope(path: str = "/workload") -> Scope:
    """Create a minimal HTTP ASGI scope."""
    return cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 9000),
        },
    )


async def receive() -> Message:
    """Return a terminal request body."""
    return {"type": "http.request", "body": b"", "more_body": False}


async def send(message: Message) -> None:
    """Accept an ASGI response message."""
    _ = message


def sample_value(metrics: RuntimeMetrics, name: str, labels: dict[str, str]) -> float:
    """Return one parsed sample value."""
    for family in text_string_to_metric_families(metrics.render().decode()):
        for sample in family.samples:
            if sample.name == name and sample.labels == labels:
                return sample.value

    raise AssertionError(f"Metric sample {name!r} with {labels!r} was not found.")


def test_completed_request_records_terminal_status() -> None:
    metrics = RuntimeMetrics()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        _ = (scope, receive)
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    middleware = RequestMetricsMiddleware(cast(ASGIApp, application), metrics=metrics)
    asyncio.run(middleware(http_scope(), receive, send))

    assert (
        sample_value(
            metrics,
            "trussium_http_requests_total",
            {"method": "POST", "outcome": "completed", "status_code": "201"},
        )
        == 1
    )
    assert sample_value(metrics, "trussium_http_requests_active", {}) == 0


def test_failed_request_records_failure_and_restores_gauge() -> None:
    metrics = RuntimeMetrics()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        _ = (scope, receive, send)
        raise RuntimeError("failed")

    middleware = RequestMetricsMiddleware(cast(ASGIApp, application), metrics=metrics)

    with pytest.raises(RuntimeError, match="failed"):
        asyncio.run(middleware(http_scope(), receive, send))

    assert (
        sample_value(
            metrics,
            "trussium_http_requests_total",
            {"method": "POST", "outcome": "failed", "status_code": "500"},
        )
        == 1
    )
    assert sample_value(metrics, "trussium_http_requests_active", {}) == 0


@pytest.mark.parametrize("exception", [CancelledError(), ClientDisconnect()])
def test_cancelled_request_records_cancellation(exception: BaseException) -> None:
    metrics = RuntimeMetrics()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        _ = (scope, receive, send)
        raise exception

    middleware = RequestMetricsMiddleware(cast(ASGIApp, application), metrics=metrics)

    with pytest.raises(type(exception)):
        asyncio.run(middleware(http_scope(), receive, send))

    assert (
        sample_value(
            metrics,
            "trussium_http_requests_total",
            {"method": "POST", "outcome": "cancelled", "status_code": "499"},
        )
        == 1
    )
    assert sample_value(metrics, "trussium_http_requests_active", {}) == 0


def test_metrics_and_health_paths_are_excluded() -> None:
    metrics = RuntimeMetrics()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        _ = (scope, receive, send)

    middleware = RequestMetricsMiddleware(cast(ASGIApp, application), metrics=metrics)

    for path in ("/metrics", "/health/live", "/health/ready"):
        asyncio.run(middleware(http_scope(path), receive, send))

    rendered = metrics.render().decode()
    assert "trussium_http_requests_total{" not in rendered
    assert "trussium_http_request_duration_seconds_count{" not in rendered
