"""Production server configuration tests."""

from fastapi import FastAPI

from trussium.config.settings import RuntimeSettings
from trussium.runtime.server import (
    GracefulShutdownServer,
    create_server,
)


def test_create_server_applies_runtime_settings() -> None:
    """The typed drain deadline should reach Uvicorn's server config."""
    application = FastAPI()
    settings = RuntimeSettings(
        host="127.0.0.1",
        port=9042,
        graceful_shutdown_seconds=7,
    )

    server = create_server(
        application,
        settings=settings,
    )

    assert isinstance(server, GracefulShutdownServer)
    assert server.config.app is application
    assert server.config.host == "127.0.0.1"
    assert server.config.port == 9042
    assert server.config.timeout_graceful_shutdown == 7
