"""Tests for runtime dependency bootstrap."""

import pytest

from trussium.app.bootstrap import (
    create_chat_capability_from_environment,
)
from trussium.providers.openai import OpenAIChatCapability


def test_missing_openai_api_key_disables_chat_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime should start without an OpenAI API key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    capability = create_chat_capability_from_environment()

    assert capability is None


def test_openai_api_key_enables_openai_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An OpenAI API key should enable the OpenAI adapter."""
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-api-key",
    )

    capability = create_chat_capability_from_environment()

    assert isinstance(capability, OpenAIChatCapability)
