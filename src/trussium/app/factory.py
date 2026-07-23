"""Application factory."""

from fastapi import FastAPI

from trussium.api import api_router
from trussium.config.settings import Settings, get_settings


def create_application(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Trussium FastAPI application.

    Args:
        settings: Optional application settings. When omitted, settings are
            loaded from the configured environment.

    Returns:
        A configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Trussium",
        description="Cloud-native AI runtime platform.",
        debug=settings.runtime.debug,
    )

    app.state.settings = settings
    app.include_router(api_router)

    return app
