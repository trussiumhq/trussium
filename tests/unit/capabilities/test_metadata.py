"""Tests for bounded provider-neutral capability metadata."""

from dataclasses import FrozenInstanceError

import pytest

from trussium.capabilities import (
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    CapabilityMetadata,
)


def test_metadata_is_immutable_and_canonical_chat_metadata_is_public() -> None:
    """Known chat discovery should have one stable provider-neutral contract."""
    expected = CapabilityMetadata(
        name=CHAT_CAPABILITY_NAME,
        version="v1",
        description="Create normalized provider-neutral chat completions.",
        supports_streaming=True,
    )
    assert expected == CHAT_CAPABILITY_METADATA

    with pytest.raises(FrozenInstanceError):
        CHAT_CAPABILITY_METADATA.version = "v2"  # type: ignore[misc]


def test_minimal_name_only_metadata_is_valid() -> None:
    """Future legacy registrations should not invent unsupported declarations."""
    metadata = CapabilityMetadata(name="future.embeddings")

    assert metadata.name == "future.embeddings"
    assert metadata.version is None
    assert metadata.description is None
    assert metadata.supports_streaming is None


@pytest.mark.parametrize("name", ["", "UPPER", "has space", "a" * 65])
def test_metadata_reuses_bounded_capability_names(name: str) -> None:
    """Metadata and implementation registration must share one identity contract."""
    with pytest.raises(ValueError, match="Capability name must match"):
        CapabilityMetadata(name=name)


@pytest.mark.parametrize("version", ["", "V1", "has space", "a" * 33])
def test_metadata_rejects_invalid_versions(version: str) -> None:
    """Externally visible protocol versions should remain bounded and stable."""
    with pytest.raises(ValueError, match="metadata version must match"):
        CapabilityMetadata(name="future.embeddings", version=version)


@pytest.mark.parametrize(
    "description",
    ["", " padded", "padded ", "line\nbreak", "control\x7f", "a" * 161],
)
def test_metadata_rejects_unbounded_or_controlled_descriptions(description: str) -> None:
    """Discovery descriptions must be bounded single-line public text."""
    with pytest.raises(ValueError, match="metadata description must be stripped"):
        CapabilityMetadata(name="future.embeddings", description=description)


def test_metadata_requires_a_real_streaming_boolean() -> None:
    """Integers and other truthy values must not become public feature declarations."""
    with pytest.raises(ValueError, match="supports_streaming must be a boolean"):
        CapabilityMetadata(
            name="future.embeddings",
            supports_streaming=1,  # type: ignore[arg-type]
        )
