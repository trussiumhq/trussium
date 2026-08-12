"""Application-scoped OpenTelemetry tracing runtime."""

from collections.abc import Sequence

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import NoOpTracerProvider, Tracer

from trussium import __version__
from trussium.config.settings import ObservabilitySettings
from trussium.observability.logging import get_logger
from trussium.observability.operations import TRACE_EXPORT_FAILED


class OperationalSpanExporter(SpanExporter):
    """Add bounded structured failure events around a span exporter."""

    def __init__(
        self,
        exporter: SpanExporter,
    ) -> None:
        """Wrap an exporter without changing its success behavior."""
        self._exporter = exporter
        self._logger = get_logger("observability")

    def export(
        self,
        spans: Sequence[ReadableSpan],
    ) -> SpanExportResult:
        """Export spans and report failures without sensitive payloads."""
        try:
            result = self._exporter.export(spans)
        except Exception as error:
            self._logger.error(
                "Trace export failed",
                extra={
                    "event": TRACE_EXPORT_FAILED,
                    "error_code": "trace_export_failed",
                    "error_type": type(error).__name__,
                    "span_count": len(spans),
                },
            )
            return SpanExportResult.FAILURE

        if result is SpanExportResult.FAILURE:
            self._logger.error(
                "Trace export failed",
                extra={
                    "event": TRACE_EXPORT_FAILED,
                    "error_code": "trace_export_failed",
                    "span_count": len(spans),
                },
            )

        return result

    def shutdown(self) -> None:
        """Shut down the wrapped exporter."""
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """Flush the wrapped exporter."""
        return self._exporter.force_flush(timeout_millis)


class RuntimeTracing:
    """Own an isolated tracer provider and its export lifecycle."""

    def __init__(
        self,
        settings: ObservabilitySettings,
        *,
        span_processor: SpanProcessor | None = None,
    ) -> None:
        """Configure no-op or exporting application tracing."""
        self._provider: TracerProvider | None = None
        self._shutdown = False

        if not settings.tracing_enabled:
            self.tracer: Tracer = NoOpTracerProvider().get_tracer(
                "trussium",
                __version__,
            )
            return

        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.tracing_service_name,
                    "service.version": __version__,
                }
            ),
            sampler=ParentBased(
                root=TraceIdRatioBased(settings.tracing_sample_ratio),
            ),
        )
        processor = (
            span_processor
            if span_processor is not None
            else BatchSpanProcessor(
                OperationalSpanExporter(
                    OTLPSpanExporter(
                        endpoint=str(settings.otlp_traces_endpoint),
                        timeout=settings.otlp_export_timeout_seconds,
                    )
                )
            )
        )
        provider.add_span_processor(processor)

        self._provider = provider
        self.tracer = provider.get_tracer(
            "trussium",
            __version__,
        )

    @property
    def enabled(self) -> bool:
        """Return whether this runtime owns an active SDK provider."""
        return self._provider is not None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """Flush pending spans when tracing is enabled."""
        if self._provider is None or self._shutdown:
            return True

        return self._provider.force_flush(timeout_millis)

    def shutdown(self) -> None:
        """Shut down the owned provider exactly once."""
        if self._provider is None or self._shutdown:
            return

        self._shutdown = True
        self._provider.shutdown()
