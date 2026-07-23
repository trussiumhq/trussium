"""Trussium runtime entry point."""

import uvicorn

from trussium.app import create_application


def main() -> None:
    """Start the Trussium runtime."""
    app = create_application()

    uvicorn.run(
        app,
        host=app.state.settings.runtime.host,
        port=app.state.settings.runtime.port,
    )


if __name__ == "__main__":
    main()
