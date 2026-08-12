"""Tests for privacy-bounded outbound trace propagation."""

from opentelemetry import baggage, context, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import (
    NonRecordingSpan,
    NoOpTracerProvider,
    SpanContext,
    SpanKind,
    TraceFlags,
    TraceState,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from trussium.config.settings import ObservabilitySettings
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.observability.tracing import RuntimeTracing

_TRACE_ID = int("0af7651916cd43dd8448eb211c80319c", 16)
_SPAN_ID = int("b7ad6b7169203331", 16)


def _span(*, sampled: bool, trace_state: TraceState | None = None) -> NonRecordingSpan:
    return NonRecordingSpan(
        SpanContext(
            trace_id=_TRACE_ID,
            span_id=_SPAN_ID,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED if sampled else TraceFlags.DEFAULT),
            trace_state=trace_state or TraceState(),
        )
    )


def test_no_valid_active_span_produces_no_headers() -> None:
    assert outbound_trace_context_headers() is None


def test_disabled_noop_tracing_does_not_forward_inbound_context() -> None:
    parent = TraceContextTextMapPropagator().extract(
        carrier={"traceparent": ("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")}
    )
    tracer = NoOpTracerProvider().get_tracer("disabled-test")

    with tracer.start_as_current_span("disabled", context=parent):
        assert outbound_trace_context_headers() is None


def test_sampled_context_is_injected_and_extractable_downstream() -> None:
    with trace.use_span(_span(sampled=True), end_on_exit=False):
        headers = outbound_trace_context_headers()

    assert headers == {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}

    extracted = TraceContextTextMapPropagator().extract(carrier=headers)
    downstream_parent = trace.get_current_span(extracted).get_span_context()
    assert downstream_parent.is_remote is True
    assert downstream_parent.trace_id == _TRACE_ID
    assert downstream_parent.span_id == _SPAN_ID
    assert downstream_parent.trace_flags.sampled is True


def test_unsampled_context_and_tracestate_are_preserved() -> None:
    trace_state = TraceState([("vendor", "opaque-value")])

    with trace.use_span(
        _span(sampled=False, trace_state=trace_state),
        end_on_exit=False,
    ):
        headers = outbound_trace_context_headers()

    assert headers == {
        "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-00",
        "tracestate": "vendor=opaque-value",
    }


def test_app_scoped_unsampled_span_propagates_without_export() -> None:
    exporter = InMemorySpanExporter()
    tracing = RuntimeTracing(
        ObservabilitySettings(
            tracing_enabled=True,
            tracing_sample_ratio=0.0,
        ),
        span_processor=SimpleSpanProcessor(exporter),
    )

    with tracing.tracer.start_as_current_span(
        "trussium.provider.chat",
        kind=SpanKind.CLIENT,
    ) as provider_span:
        headers = outbound_trace_context_headers()

    assert headers is not None
    _, trace_id, parent_span_id, trace_flags = headers["traceparent"].split("-")
    assert trace_id == f"{provider_span.get_span_context().trace_id:032x}"
    assert parent_span_id == f"{provider_span.get_span_context().span_id:016x}"
    assert int(trace_flags, 16) & 0x01 == 0
    assert exporter.get_finished_spans() == ()

    tracing.shutdown()


def test_baggage_is_not_injected_into_provider_headers() -> None:
    baggage_context = baggage.set_baggage(
        "private-user-data",
        "must-not-leave-runtime",
    )
    combined_context = trace.set_span_in_context(
        _span(sampled=True),
        baggage_context,
    )
    token = context.attach(combined_context)

    try:
        headers = outbound_trace_context_headers()
    finally:
        context.detach(token)

    assert headers is not None
    assert set(headers) == {"traceparent"}
    assert "must-not-leave-runtime" not in repr(headers)


def test_receiver_server_span_continues_the_provider_client_trace() -> None:
    """A downstream service should extract a child of the provider span."""
    provider_exporter = InMemorySpanExporter()
    receiver_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    receiver = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(provider_exporter))
    receiver.add_span_processor(SimpleSpanProcessor(receiver_exporter))

    with provider.get_tracer("provider-test").start_as_current_span(
        "trussium.provider.chat",
        kind=SpanKind.CLIENT,
    ) as provider_span:
        headers = outbound_trace_context_headers()
        assert headers is not None
        extracted = TraceContextTextMapPropagator().extract(carrier=headers)

        with receiver.get_tracer("receiver-test").start_as_current_span(
            "provider.responses",
            context=extracted,
            kind=SpanKind.SERVER,
        ):
            pass

    receiver_span = receiver_exporter.get_finished_spans()[0]
    assert receiver_span.parent is not None
    assert receiver_span.context.trace_id == provider_span.get_span_context().trace_id
    assert receiver_span.parent.span_id == provider_span.get_span_context().span_id
    assert receiver_span.parent.is_remote is True

    provider.shutdown()
    receiver.shutdown()
