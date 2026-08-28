"""Application factory."""

from asyncio import CancelledError
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from trussium.api import api_router
from trussium.api.errors import request_validation_exception_handler
from trussium.api.metrics import router as metrics_router
from trussium.capabilities import (
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    CapabilityAvailabilityReporter,
    CapabilityContractMismatchError,
    CapabilityExecutionPipeline,
    CapabilityHealthReporter,
    CapabilityLifecycle,
    CapabilityMiddleware,
    CapabilityRegistry,
)
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
from trussium.providers import (
    ProviderHealthReporter,
    ProviderLifecycle,
    ProviderRegistry,
    ProviderRouter,
    RetryPolicy,
)
from trussium.runtime import (
    DependencyHealthCheck,
    DependencyReadiness,
    RuntimeComponentHealthReporter,
    RuntimeService,
    RuntimeServiceLifecycle,
    RuntimeServiceRegistry,
)
from trussium.tools import ToolExecutor


def create_application(
    settings: Settings | None = None,
    *,
    chat_capability: ChatCapability | None = None,
    capability_registry: CapabilityRegistry | None = None,
    provider_registry: ProviderRegistry | None = None,
    provider_lifecycle: ProviderLifecycle | None = None,
    capability_middleware: Sequence[CapabilityMiddleware] = (),
    tracing: RuntimeTracing | None = None,
    dependency_health_check: DependencyHealthCheck | None = None,
    runtime_services: Sequence[RuntimeService] = (),
    runtime_service_registry: RuntimeServiceRegistry | None = None,
    tool_executor: ToolExecutor | None = None,
) -> FastAPI:
    """Create and configure the Trussium application.

    Args:
        settings: Optional runtime settings override.
        chat_capability: Optional configured chat capability.
        capability_registry: Optional provider-neutral capability registrations.
        capability_middleware: Ordered provider-neutral capability middleware.
        tracing: Optional shared application tracing runtime.
        dependency_health_check: Optional configured provider dependency check.
        runtime_services: Ordered runtime services managed by application lifespan.
        runtime_service_registry: Optional preconfigured runtime-service registry.
        tool_executor: Optional allowlisted in-process tool executor.

    Returns:
        Configured FastAPI application.
    """
    resolved_settings = settings or get_settings()
    resolved_provider_registry = provider_registry or ProviderRegistry()
    resolved_provider_registry.seal()
    provider_health_reporter = ProviderHealthReporter(resolved_provider_registry)
    provider_router = ProviderRouter(
        resolved_provider_registry,
        resolved_settings.routing.provider_priority,
    )
    resolved_provider_lifecycle = provider_lifecycle or ProviderLifecycle()

    if capability_registry is not None and chat_capability is not None:
        raise ValueError("chat_capability and capability_registry are mutually exclusive")

    if runtime_service_registry is not None and runtime_services:
        raise ValueError("runtime_services and runtime_service_registry are mutually exclusive")

    resolved_runtime_service_registry = (
        runtime_service_registry
        if runtime_service_registry is not None
        else RuntimeServiceRegistry(runtime_services)
    )
    registered_runtime_services = resolved_runtime_service_registry.seal()

    configure_logging(
        debug=resolved_settings.runtime.debug,
    )
    runtime_tracing = tracing or RuntimeTracing(
        resolved_settings.observability,
    )
    configured_capability_registry = (
        capability_registry if capability_registry is not None else CapabilityRegistry()
    )
    if chat_capability is not None:
        configured_capability_registry.register(
            CHAT_CAPABILITY_NAME,
            chat_capability,
            metadata=CHAT_CAPABILITY_METADATA,
        )

    configured_registrations = configured_capability_registry.seal()
    capability_availability_reporter = CapabilityAvailabilityReporter(
        configured_capability_registry,
        timeout_seconds=(resolved_settings.runtime.capability_availability_timeout_seconds),
    )
    capability_health_reporter = CapabilityHealthReporter(
        configured_capability_registry,
        timeout_seconds=resolved_settings.runtime.capability_health_timeout_seconds,
    )
    capability_lifecycle = CapabilityLifecycle(
        configured_capability_registry,
        cleanup_timeout_seconds=resolved_settings.runtime.service_cleanup_seconds,
    )
    resolved_capability_registry = CapabilityRegistry()
    for registration in configured_registrations:
        capability = registration.capability
        metadata = registration.metadata
        if registration.name == CHAT_CAPABILITY_NAME:
            if not isinstance(capability, ChatCapability):
                raise CapabilityContractMismatchError(registration.name)
            if not isinstance(capability, LoggingChatCapability):
                capability = LoggingChatCapability(
                    capability,
                    tracer=runtime_tracing.tracer,
                )
            metadata = CHAT_CAPABILITY_METADATA

        resolved_capability_registry.register(
            registration.name,
            capability,
            metadata=metadata,
        )

    resolved_capability_registry.seal()
    capability_execution_pipeline = CapabilityExecutionPipeline(
        resolved_capability_registry,
        middleware=capability_middleware,
        retry_policy=RetryPolicy(
            max_attempts=resolved_settings.retries.max_attempts,
            base_delay_seconds=resolved_settings.retries.base_delay_seconds,
            max_delay_seconds=resolved_settings.retries.max_delay_seconds,
        ),
        timeout_seconds=resolved_settings.timeouts.provider_request_seconds,
    )
    resolved_chat_capability = resolved_capability_registry.get(CHAT_CAPABILITY_NAME)
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
    runtime_service_lifecycle = RuntimeServiceLifecycle(
        registered_runtime_services,
        cleanup_timeout_seconds=resolved_settings.runtime.service_cleanup_seconds,
    )
    runtime_component_health_reporter = RuntimeComponentHealthReporter(
        resolved_runtime_service_registry,
        timeout_seconds=resolved_settings.runtime.component_health_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        started_at = perf_counter()
        startup_error: BaseException | None = None
        capabilities_started = False
        providers_started = False
        runtime_services_started = False
        runtime_started = False
        log_startup_configuration(
            resolved_settings,
            provider_configured=resolved_chat_capability is not None,
        )

        try:
            try:
                await runtime_service_lifecycle.startup()
            except BaseException as error:
                startup_error = error
                raise

            runtime_services_started = True
            try:
                await resolved_provider_lifecycle.startup()
            except BaseException as error:
                startup_error = error
                raise

            providers_started = True
            try:
                await capability_lifecycle.startup()
            except BaseException as error:
                startup_error = error
                raise

            capabilities_started = True
            runtime_started = True
            runtime_logger.info(
                "Runtime started",
                extra={
                    "event": RUNTIME_STARTED,
                },
            )
            yield
        finally:
            if runtime_started:
                runtime_logger.info(
                    "Runtime stopping",
                    extra={
                        "event": RUNTIME_STOPPING,
                    },
                )

            capability_shutdown_error: BaseException | None = None
            provider_shutdown_error: BaseException | None = None
            lifecycle_shutdown_error: BaseException | None = None
            dependency_shutdown_error: Exception | None = None
            tracing_shutdown_error: Exception | None = None

            if capabilities_started:
                try:
                    await capability_lifecycle.shutdown()
                except BaseException as error:
                    capability_shutdown_error = error

            if providers_started:
                try:
                    await resolved_provider_lifecycle.shutdown()
                except BaseException as error:
                    provider_shutdown_error = error

            if runtime_services_started:
                try:
                    await runtime_service_lifecycle.shutdown()
                except BaseException as error:
                    lifecycle_shutdown_error = error

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
                tracing_shutdown_error = error
                runtime_logger.error(
                    "Tracing shutdown failed",
                    extra={
                        "event": TRACING_SHUTDOWN_FAILED,
                        "error_code": "tracing_shutdown_failed",
                        "error_type": type(error).__name__,
                    },
                )
            else:
                runtime_logger.info(
                    "Tracing shutdown completed",
                    extra={
                        "event": TRACING_SHUTDOWN_COMPLETED,
                        "tracing_enabled": runtime_tracing.enabled,
                        "outcome": "completed" if runtime_tracing.enabled else "disabled",
                    },
                )

            terminal_error: BaseException | None = None
            if startup_error is None:
                if isinstance(capability_shutdown_error, CancelledError):
                    terminal_error = capability_shutdown_error
                elif isinstance(lifecycle_shutdown_error, CancelledError):
                    terminal_error = lifecycle_shutdown_error
                elif tracing_shutdown_error is not None:
                    terminal_error = tracing_shutdown_error
                elif capability_shutdown_error is not None:
                    terminal_error = capability_shutdown_error
                elif lifecycle_shutdown_error is not None:
                    terminal_error = lifecycle_shutdown_error
                elif provider_shutdown_error is not None:
                    terminal_error = provider_shutdown_error
                elif dependency_shutdown_error is not None:
                    terminal_error = dependency_shutdown_error

            if startup_error is not None or terminal_error is not None:
                runtime_logger.error(
                    "Runtime stopped with an operational failure",
                    extra={
                        "event": RUNTIME_STOPPED,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                        "outcome": "failed",
                    },
                )
                if terminal_error is not None:
                    raise terminal_error
            else:
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
        exception_handlers={RequestValidationError: request_validation_exception_handler},
    )
    if tool_executor is not None:
        application.state.tool_executor = tool_executor

    application.state.settings = resolved_settings
    application.state.model_aliases = dict(resolved_settings.runtime.model_aliases)
    application.state.runtime_tracing = runtime_tracing
    application.state.dependency_readiness = dependency_readiness
    application.state.runtime_service_lifecycle = runtime_service_lifecycle
    application.state.runtime_service_registry = resolved_runtime_service_registry
    application.state.runtime_component_health_reporter = runtime_component_health_reporter
    application.state.capability_registry = resolved_capability_registry
    application.state.provider_registry = resolved_provider_registry
    application.state.provider_health_reporter = provider_health_reporter
    application.state.provider_router = provider_router
    application.state.provider_fallback = provider_router.execute_with_fallback
    application.state.provider_lifecycle = resolved_provider_lifecycle
    application.state.capability_availability_reporter = capability_availability_reporter
    application.state.capability_health_reporter = capability_health_reporter
    application.state.capability_lifecycle = capability_lifecycle
    application.state.capability_execution_pipeline = capability_execution_pipeline
    application.state.chat_capability = resolved_chat_capability

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
