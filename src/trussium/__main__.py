"""Trussium runtime entry point."""

import uvicorn

from trussium.app import create_application
from trussium.app.bootstrap import (
    create_chat_capability_from_environment,
)
from trussium.config.settings import get_settings


def main() -> None:
    """Start the Trussium runtime."""
    settings = get_settings()
    chat_capability = create_chat_capability_from_environment()

    app = create_application(
        settings=settings,
        chat_capability=chat_capability,
    )

    uvicorn.run(
        app,
        host=settings.runtime.host,
        port=settings.runtime.port,
    )


if __name__ == "__main__":
    main()
