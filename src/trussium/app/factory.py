"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from trussium.api import api_router
from trussium.api.metrics import router as metrics_router
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import Settings, get_settings
from trussium.middleware import (
    RequestCorrelationMiddleware,
    RequestLoggingMiddleware,
    RequestMetricsMiddleware,
    RequestTracingMiddleware,
)
from trussium.observability import (
    LoggingChatCapability,
    RuntimeMetrics,
    RuntimeTracing,
    configure_logging,
)


def create_application(
    settings: Settings | None = None,
    *,
    chat_capability: ChatCapability | None = None,
    tracing: RuntimeTracing | None = None,
) -> FastAPI:
    """Create and configure the Trussium application.

    Args:
        settings: Optional runtime settings override.
        chat_capability: Optional configured chat capability.
        tracing: Optional shared application tracing runtime.

    Returns:
        Configured FastAPI application.
    """
    resolved_settings = settings or get_settings()

    configure_logging(
        debug=resolved_settings.runtime.debug,
    )
    runtime_tracing = tracing or RuntimeTracing(
        resolved_settings.observability,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            runtime_tracing.shutdown()

    application = FastAPI(
        title="Trussium",
        debug=resolved_settings.runtime.debug,
        lifespan=lifespan,
    )

    application.state.settings = resolved_settings
    application.state.runtime_tracing = runtime_tracing
    application.state.chat_capability = (
        LoggingChatCapability(
            chat_capability,
            tracer=runtime_tracing.tracer,
        )
        if chat_capability is not None
        and not isinstance(
            chat_capability,
            LoggingChatCapability,
        )
        else chat_capability
    )

    if resolved_settings.observability.metrics_enabled:
        runtime_metrics = RuntimeMetrics()
        application.state.runtime_metrics = runtime_metrics
        application.add_middleware(
            RequestMetricsMiddleware,
            metrics=runtime_metrics,
        )
        application.include_router(metrics_router)

    application.add_middleware(
        RequestLoggingMiddleware,
    )

    if runtime_tracing.enabled:
        application.add_middleware(
            RequestTracingMiddleware,
            tracer=runtime_tracing.tracer,
        )

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    application.include_router(api_router)

    return application
