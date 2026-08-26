"""Tests for provider interface and metadata contracts."""

from dataclasses import FrozenInstanceError

import pytest

from trussium.providers import Provider, ProviderMetadata, validate_provider_name


def test_provider_metadata_is_immutable() -> None:
    metadata = ProviderMetadata(
        name="self-hosted",
        version="1.2.3",
        capabilities=("chat.completions", "audio.speech"),
    )

    assert metadata.capabilities == ("chat.completions", "audio.speech")
    with pytest.raises(FrozenInstanceError):
        metadata.name = "other"  # type: ignore[misc]


@pytest.mark.parametrize("name", ["", "OpenAI", "provider/name", "a" * 65])
def test_provider_name_is_bounded(name: str) -> None:
    with pytest.raises(ValueError):
        validate_provider_name(name)


@pytest.mark.parametrize(
    ("field", "value"),
    [("version", ""), ("version", "bad version"), ("capabilities", ("bad/name",))],
)
def test_provider_metadata_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        values = {"name": "openai", "version": "1.0.0", field: value}
        ProviderMetadata(**values)  # type: ignore[arg-type]


def test_provider_metadata_rejects_duplicate_capabilities() -> None:
    with pytest.raises(ValueError, match="unique"):
        ProviderMetadata(name="openai", version="1.0.0", capabilities=("chat.completions",) * 2)


def test_provider_protocol_is_runtime_checkable() -> None:
    class FakeProvider:
        metadata = ProviderMetadata(name="fake", version="0.1.0")
        capabilities: tuple[object, ...] = ()

    assert isinstance(FakeProvider(), Provider)
