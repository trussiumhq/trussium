"""Trussium runtime entry point."""

from pydantic import ValidationError

from trussium.app import create_application
from trussium.app.bootstrap import (
    create_chat_capability_from_environment,
    create_provider_health_check_from_environment,
)
from trussium.config.settings import get_settings
from trussium.observability import (
    RUNTIME_CONFIGURATION_INVALID,
    RuntimeTracing,
    configure_logging,
    get_logger,
)
from trussium.runtime.server import create_server


def main() -> None:
    """Start the Trussium runtime."""
    configure_logging()

    try:
        settings = get_settings()
    except ValidationError as error:
        get_logger("runtime").error(
            "Runtime configuration is invalid",
            extra={
                "event": RUNTIME_CONFIGURATION_INVALID,
                "error_code": "invalid_configuration",
                "error_count": error.error_count(),
                "error_type": type(error).__name__,
            },
        )
        raise SystemExit(2) from None

    configure_logging(
        debug=settings.runtime.debug,
    )
    tracing = RuntimeTracing(settings.observability)
    chat_capability = create_chat_capability_from_environment(
        provider=settings.provider,
        timeouts=settings.timeouts,
        tracer=tracing.tracer,
    )
    dependency_health_check = create_provider_health_check_from_environment(
        provider=settings.provider,
        readiness=settings.readiness,
    )

    app = create_application(
        settings=settings,
        chat_capability=chat_capability,
        tracing=tracing,
        dependency_health_check=dependency_health_check,
    )

    server = create_server(
        app,
        settings=settings.runtime,
    )
    server.run()


if __name__ == "__main__":
    main()
