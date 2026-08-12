"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

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
    RUNTIME_STARTED,
    RUNTIME_STOPPED,
    RUNTIME_STOPPING,
    TRACING_SHUTDOWN_COMPLETED,
    TRACING_SHUTDOWN_FAILED,
    LoggingChatCapability,
    RuntimeMetrics,
    RuntimeTracing,
    configure_logging,
    get_logger,
    log_startup_configuration,
)
from trussium.runtime import DependencyHealthCheck, DependencyReadiness


def create_application(
    settings: Settings | None = None,
    *,
    chat_capability: ChatCapability | None = None,
    tracing: RuntimeTracing | None = None,
    dependency_health_check: DependencyHealthCheck | None = None,
) -> FastAPI:
    """Create and configure the Trussium application.

    Args:
        settings: Optional runtime settings override.
        chat_capability: Optional configured chat capability.
        tracing: Optional shared application tracing runtime.
        dependency_health_check: Optional configured provider dependency check.

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
    runtime_logger = get_logger("runtime")
    dependency_readiness = (
        DependencyReadiness(
            dependency_health_check,
            timeout_seconds=resolved_settings.readiness.dependency_timeout_seconds,
            cache_seconds=resolved_settings.readiness.dependency_cache_seconds,
        )
        if dependency_health_check is not None
        else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        started_at = perf_counter()
        log_startup_configuration(
            resolved_settings,
            provider_configured=chat_capability is not None,
        )
        runtime_logger.info(
            "Runtime started",
            extra={
                "event": RUNTIME_STARTED,
            },
        )

        try:
            yield
        finally:
            runtime_logger.info(
                "Runtime stopping",
                extra={
                    "event": RUNTIME_STOPPING,
                },
            )

            dependency_shutdown_error: Exception | None = None

            if dependency_readiness is not None:
                try:
                    await dependency_readiness.close()
                except Exception as error:
                    dependency_shutdown_error = error
                    runtime_logger.error(
                        "Readiness dependency shutdown failed",
                        extra={
                            "event": "readiness.dependency.shutdown.failed",
                            "error_code": "readiness_dependency_shutdown_failed",
                            "error_type": type(error).__name__,
                        },
                    )

            try:
                runtime_tracing.shutdown()
            except Exception as error:
                runtime_logger.error(
                    "Tracing shutdown failed",
                    extra={
                        "event": TRACING_SHUTDOWN_FAILED,
                        "error_code": "tracing_shutdown_failed",
                        "error_type": type(error).__name__,
                    },
                )
                runtime_logger.error(
                    "Runtime stopped with an operational failure",
                    extra={
                        "event": RUNTIME_STOPPED,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                        "outcome": "failed",
                    },
                )
                raise

            runtime_logger.info(
                "Tracing shutdown completed",
                extra={
                    "event": TRACING_SHUTDOWN_COMPLETED,
                    "tracing_enabled": runtime_tracing.enabled,
                    "outcome": "completed" if runtime_tracing.enabled else "disabled",
                },
            )

            if dependency_shutdown_error is not None:
                runtime_logger.error(
                    "Runtime stopped with an operational failure",
                    extra={
                        "event": RUNTIME_STOPPED,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                        "outcome": "failed",
                    },
                )
                raise dependency_shutdown_error

            runtime_logger.info(
                "Runtime stopped",
                extra={
                    "event": RUNTIME_STOPPED,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                    "outcome": "completed",
                },
            )

    application = FastAPI(
        title="Trussium",
        debug=resolved_settings.runtime.debug,
        lifespan=lifespan,
    )

    application.state.settings = resolved_settings
    application.state.runtime_tracing = runtime_tracing
    application.state.dependency_readiness = dependency_readiness
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
