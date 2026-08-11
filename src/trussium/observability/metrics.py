"""Prometheus-compatible runtime metrics."""

from typing import Final

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)

METRICS_CONTENT_TYPE: Final = CONTENT_TYPE_LATEST

_REQUEST_DURATION_BUCKETS: Final[tuple[float, ...]] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
)


class RuntimeMetrics:
    """Application-scoped runtime metric registry and instruments."""

    def __init__(self) -> None:
        """Create an isolated registry with runtime and process collectors."""
        self.registry = CollectorRegistry()
        GCCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        ProcessCollector(registry=self.registry)

        self.http_requests_active = Gauge(
            "trussium_http_requests_active",
            "Number of active Trussium workload HTTP requests.",
            registry=self.registry,
        )
        self.http_requests_total = Counter(
            "trussium_http_requests",
            "Total Trussium workload HTTP requests.",
            labelnames=("method", "outcome", "status_code"),
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "trussium_http_request_duration_seconds",
            "Trussium workload HTTP request duration in seconds.",
            labelnames=("method", "outcome"),
            buckets=_REQUEST_DURATION_BUCKETS,
            registry=self.registry,
        )

    def request_started(self) -> None:
        """Record that a workload request became active."""
        self.http_requests_active.inc()

    def request_finished(
        self,
        *,
        method: str,
        outcome: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record a terminal workload request result."""
        self.http_requests_active.dec()
        self.http_requests_total.labels(
            method=method,
            outcome=outcome,
            status_code=str(status_code),
        ).inc()
        self.http_request_duration_seconds.labels(
            method=method,
            outcome=outcome,
        ).observe(duration_seconds)

    def render(self) -> bytes:
        """Render the registry in Prometheus text exposition format."""
        return generate_latest(self.registry)
