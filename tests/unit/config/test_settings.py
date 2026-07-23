from trussium.config.settings import Environment, Settings


def test_default_settings() -> None:
    settings = Settings()

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.runtime.host == "0.0.0.0"
    assert settings.runtime.port == 8080
    assert settings.runtime.debug is False
