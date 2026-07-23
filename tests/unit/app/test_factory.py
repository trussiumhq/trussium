from fastapi import FastAPI

from trussium.app import create_application
from trussium.config.settings import Settings


def test_create_application_returns_fastapi() -> None:
    app = create_application()

    assert isinstance(app, FastAPI)


def test_application_contains_settings() -> None:
    app = create_application()

    assert isinstance(app.state.settings, Settings)


def test_application_debug_matches_settings() -> None:
    settings = Settings()

    app = create_application(settings)

    assert app.debug is settings.runtime.debug


def test_application_title() -> None:
    app = create_application()

    assert app.title == "Trussium"
