"""Privacy-bounded outbound W3C Trace Context propagation."""

from typing import Final

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_TRACE_CONTEXT_PROPAGATOR: Final = TraceContextTextMapPropagator()


def outbound_trace_context_headers() -> dict[str, str] | None:
    """Return W3C headers for the current valid local span, when one exists.

    The explicit Trace Context propagator intentionally excludes OpenTelemetry
    baggage and any process-global propagator customization. This keeps provider
    requests limited to ``traceparent`` and optional ``tracestate`` metadata.
    A remote-only parent is not forwarded without a locally created provider
    span, which keeps disabled no-op tracing free of outbound trace headers.
    """
    span_context = trace.get_current_span().get_span_context()

    if not span_context.is_valid or span_context.is_remote:
        return None

    carrier: dict[str, str] = {}
    _TRACE_CONTEXT_PROPAGATOR.inject(carrier)

    return carrier or None
