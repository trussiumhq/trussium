"""Bounded structured operational event logging."""

from typing import Final

from trussium import __version__
from trussium.config.settings import Settings
from trussium.observability.logging import get_logger

RUNTIME_CONFIGURATION_INVALID: Final = "runtime.configuration.invalid"
RUNTIME_CONFIGURATION_LOADED: Final = "runtime.configuration.loaded"
PROVIDER_CONFIGURATION_READY: Final = "provider.configuration.ready"
PROVIDER_CONFIGURATION_UNAVAILABLE: Final = "provider.configuration.unavailable"
READINESS_CONFIGURATION_LOADED: Final = "readiness.configuration.loaded"
OBSERVABILITY_CONFIGURATION_LOADED: Final = "observability.configuration.loaded"
RUNTIME_STARTED: Final = "runtime.started"
RUNTIME_STOPPING: Final = "runtime.stopping"
RUNTIME_STOPPED: Final = "runtime.stopped"
TOOL_EXECUTION_STARTED: Final = "tool.execution.started"
TOOL_EXECUTION_COMPLETED: Final = "tool.execution.completed"
TOOL_EXECUTION_FAILED: Final = "tool.execution.failed"
TOOL_EXECUTION_TIMEOUT: Final = "tool.execution.timeout"
WORKFLOW_EXECUTION_STARTED: Final = "workflow.execution.started"
WORKFLOW_EXECUTION_COMPLETED: Final = "workflow.execution.completed"
WORKFLOW_EXECUTION_TIMEOUT: Final = "workflow.execution.timeout"
WORKFLOW_EXECUTION_CANCELLED: Final = "workflow.execution.cancelled"
WORKFLOW_ADMISSION_REJECTED: Final = "workflow.admission.rejected"
RUNTIME_SERVICE_STARTUP_STARTED: Final = "runtime.service.startup.started"
RUNTIME_SERVICE_STARTUP_COMPLETED: Final = "runtime.service.startup.completed"
RUNTIME_SERVICE_STARTUP_FAILED: Final = "runtime.service.startup.failed"
RUNTIME_SERVICE_STARTUP_CANCELLED: Final = "runtime.service.startup.cancelled"
RUNTIME_SERVICE_ROLLBACK_STARTED: Final = "runtime.service.rollback.started"
RUNTIME_SERVICE_ROLLBACK_COMPLETED: Final = "runtime.service.rollback.completed"
RUNTIME_SERVICE_ROLLBACK_FAILED: Final = "runtime.service.rollback.failed"
RUNTIME_SERVICE_ROLLBACK_TIMEOUT: Final = "runtime.service.rollback.timeout"
RUNTIME_SERVICE_ROLLBACK_CANCELLED: Final = "runtime.service.rollback.cancelled"
RUNTIME_SERVICE_SHUTDOWN_STARTED: Final = "runtime.service.shutdown.started"
RUNTIME_SERVICE_SHUTDOWN_COMPLETED: Final = "runtime.service.shutdown.completed"
RUNTIME_SERVICE_SHUTDOWN_FAILED: Final = "runtime.service.shutdown.failed"
RUNTIME_SERVICE_SHUTDOWN_TIMEOUT: Final = "runtime.service.shutdown.timeout"
RUNTIME_SERVICE_SHUTDOWN_CANCELLED: Final = "runtime.service.shutdown.cancelled"
CAPABILITY_STARTUP_STARTED: Final = "capability.startup.started"
CAPABILITY_STARTUP_COMPLETED: Final = "capability.startup.completed"
CAPABILITY_STARTUP_FAILED: Final = "capability.startup.failed"
CAPABILITY_STARTUP_CANCELLED: Final = "capability.startup.cancelled"
CAPABILITY_ROLLBACK_STARTED: Final = "capability.rollback.started"
CAPABILITY_ROLLBACK_COMPLETED: Final = "capability.rollback.completed"
CAPABILITY_ROLLBACK_FAILED: Final = "capability.rollback.failed"
CAPABILITY_ROLLBACK_TIMEOUT: Final = "capability.rollback.timeout"
CAPABILITY_ROLLBACK_CANCELLED: Final = "capability.rollback.cancelled"
CAPABILITY_SHUTDOWN_STARTED: Final = "capability.shutdown.started"
CAPABILITY_SHUTDOWN_COMPLETED: Final = "capability.shutdown.completed"
CAPABILITY_SHUTDOWN_FAILED: Final = "capability.shutdown.failed"
CAPABILITY_SHUTDOWN_TIMEOUT: Final = "capability.shutdown.timeout"
CAPABILITY_SHUTDOWN_CANCELLED: Final = "capability.shutdown.cancelled"
TRACING_SHUTDOWN_COMPLETED: Final = "observability.tracing.shutdown.completed"
TRACING_SHUTDOWN_FAILED: Final = "observability.tracing.shutdown.failed"
TRACE_EXPORT_FAILED: Final = "observability.trace_export.failed"
RUNTIME_SHUTDOWN_STARTED: Final = "runtime.shutdown.started"
RUNTIME_SHUTDOWN_DRAIN_TIMEOUT: Final = "runtime.shutdown.drain_timeout"
RUNTIME_SHUTDOWN_CLEANUP_TIMEOUT: Final = "runtime.shutdown.cleanup_timeout"
RUNTIME_SHUTDOWN_COMPLETED: Final = "runtime.shutdown.completed"


def log_startup_configuration(
    settings: Settings,
    *,
    provider_configured: bool,
) -> None:
    """Emit safe configuration summaries for runtime startup."""
    runtime_logger = get_logger("runtime")
    provider_logger = get_logger("provider")
    readiness_logger = get_logger("readiness")
    observability_logger = get_logger("observability")
    runtime_logger.info(
        "Runtime configuration loaded",
        extra={
            "event": RUNTIME_CONFIGURATION_LOADED,
            "runtime_version": __version__,
            "environment": settings.environment.value,
            "port": settings.runtime.port,
            "debug": settings.runtime.debug,
            "graceful_shutdown_seconds": settings.runtime.graceful_shutdown_seconds,
            "service_cleanup_seconds": settings.runtime.service_cleanup_seconds,
            "component_health_timeout_seconds": (settings.runtime.component_health_timeout_seconds),
            "capability_availability_timeout_seconds": (
                settings.runtime.capability_availability_timeout_seconds
            ),
            "capability_health_timeout_seconds": settings.runtime.capability_health_timeout_seconds,
        },
    )

    provider_event = (
        PROVIDER_CONFIGURATION_READY if provider_configured else PROVIDER_CONFIGURATION_UNAVAILABLE
    )
    provider_level = provider_logger.info if provider_configured else provider_logger.warning
    provider_level(
        "Provider configuration ready"
        if provider_configured
        else "Provider configuration unavailable",
        extra={
            "event": provider_event,
            "provider": settings.provider.name.value,
            "provider_configured": provider_configured,
        },
    )

    readiness_logger.info(
        "Readiness configuration loaded",
        extra={
            "event": READINESS_CONFIGURATION_LOADED,
            "dependency_checks_enabled": settings.readiness.dependency_checks_enabled,
            "dependency_timeout_seconds": settings.readiness.dependency_timeout_seconds,
            "dependency_cache_seconds": settings.readiness.dependency_cache_seconds,
            "required_model_configured": settings.readiness.required_model is not None,
        },
    )

    observability_logger.info(
        "Observability configuration loaded",
        extra={
            "event": OBSERVABILITY_CONFIGURATION_LOADED,
            "metrics_enabled": settings.observability.metrics_enabled,
            "tracing_enabled": settings.observability.tracing_enabled,
            "trace_sample_ratio": settings.observability.tracing_sample_ratio,
        },
    )
