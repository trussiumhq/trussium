"""Application factory."""

from fastapi import FastAPI

from trussium.config.settings import Settings, get_settings


def create_application(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Trussium application.

    Args:
        settings: Optional application settings. If omitted,
            the cached application settings are used.

    Returns:
        A configured FastAPI application instance.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Trussium",
        description="Cloud-native AI runtime platform.",
        debug=settings.runtime.debug,
    )

    # Make application settings available throughout the runtime.
    app.state.settings = settings

    return app
