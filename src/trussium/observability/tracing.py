"""Application-scoped OpenTelemetry tracing runtime."""

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import NoOpTracerProvider, Tracer

from trussium import __version__
from trussium.config.settings import ObservabilitySettings


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
                OTLPSpanExporter(
                    endpoint=str(settings.otlp_traces_endpoint),
                    timeout=settings.otlp_export_timeout_seconds,
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
