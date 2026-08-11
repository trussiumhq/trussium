"""Trussium runtime entry point."""

from trussium.app import create_application
from trussium.app.bootstrap import (
    create_chat_capability_from_environment,
)
from trussium.config.settings import get_settings
from trussium.observability import RuntimeTracing
from trussium.runtime.server import create_server


def main() -> None:
    """Start the Trussium runtime."""
    settings = get_settings()
    tracing = RuntimeTracing(settings.observability)
    chat_capability = create_chat_capability_from_environment(
        provider=settings.provider,
        timeouts=settings.timeouts,
        tracer=tracing.tracer,
    )

    app = create_application(
        settings=settings,
        chat_capability=chat_capability,
        tracing=tracing,
    )

    server = create_server(
        app,
        settings=settings.runtime,
    )
    server.run()


if __name__ == "__main__":
    main()
