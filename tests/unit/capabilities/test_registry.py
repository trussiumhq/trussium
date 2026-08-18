"""Tests for deterministic provider-neutral capability registration."""

import pytest

from trussium.capabilities import (
    CHAT_CAPABILITY_NAME,
    CapabilityAlreadyRegisteredError,
    CapabilityContractMismatchError,
    CapabilityMetadata,
    CapabilityNotFoundError,
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityRegistryError,
    CapabilityRegistrySealedError,
)
from trussium.errors import ConfigurationError, TrussiumError
from trussium.observability import CHAT_CAPABILITY_NAME as OBSERVABILITY_CHAT_CAPABILITY_NAME


def test_chat_capability_name_has_one_canonical_compatible_export() -> None:
    """Existing observability callers should resolve the capability-domain identity."""
    assert CHAT_CAPABILITY_NAME == "chat.completions"
    assert OBSERVABILITY_CHAT_CAPABILITY_NAME is CHAT_CAPABILITY_NAME


def test_registration_and_discovery_preserve_insertion_order() -> None:
    """All registry surfaces should follow explicit registration order."""
    first = object()
    second = object()
    registry = CapabilityRegistry((CapabilityRegistration("first", first),))

    registered = registry.register("second", second)

    assert registered is second
    assert registry.names == ("first", "second")
    assert registry.capabilities == (first, second)
    assert registry.registrations == (
        CapabilityRegistration("first", first),
        CapabilityRegistration("second", second),
    )
    assert tuple(registry) == registry.registrations
    assert len(registry) == 2
    assert "first" in registry
    assert "missing" not in registry
    assert object() not in registry
    assert registry.get("first") is first
    assert registry.get("missing") is None
    assert registry.require("second") is second
    assert registry.metadata == (
        CapabilityMetadata(name="first"),
        CapabilityMetadata(name="second"),
    )
    assert registry.get_metadata("first") == CapabilityMetadata(name="first")
    assert registry.get_metadata("missing") is None
    assert registry.require_metadata("second") == CapabilityMetadata(name="second")


def test_explicit_metadata_preserves_order_and_snapshot_immutability() -> None:
    """Public discovery must retain caller metadata without exposing later mutation."""
    first = object()
    second = object()
    first_metadata = CapabilityMetadata(
        name="future.embeddings",
        version="v2",
        description="Create normalized embeddings.",
        supports_streaming=False,
    )
    second_metadata = CapabilityMetadata(name="future.images", version="v1")
    registry = CapabilityRegistry(
        (CapabilityRegistration("future.embeddings", first, first_metadata),)
    )
    snapshot = registry.metadata

    registry.register("future.images", second, metadata=second_metadata)

    assert snapshot == (first_metadata,)
    assert registry.metadata == (first_metadata, second_metadata)
    assert registry.registrations[0].metadata is first_metadata
    assert registry.get_metadata("future.images") is second_metadata
    assert registry.require_metadata("future.embeddings") is first_metadata


def test_discovery_snapshots_do_not_expose_later_mutation() -> None:
    """Previously returned tuples must remain immutable and stable."""
    first = object()
    second = object()
    registry = CapabilityRegistry((CapabilityRegistration("first", first),))
    names_snapshot = registry.names
    capabilities_snapshot = registry.capabilities
    registrations_snapshot = registry.registrations

    registry.register("second", second)

    assert names_snapshot == ("first",)
    assert capabilities_snapshot == (first,)
    assert registrations_snapshot == (CapabilityRegistration("first", first),)
    assert registry.names == ("first", "second")


def test_duplicate_registration_is_typed_and_preserves_original() -> None:
    """A duplicate name must never replace or reorder the first object."""
    original = object()
    duplicate = object()
    registry = CapabilityRegistry((CapabilityRegistration("chat.completions", original),))

    with pytest.raises(CapabilityAlreadyRegisteredError) as captured:
        registry.register("chat.completions", duplicate)

    error = captured.value
    assert isinstance(error, CapabilityRegistryError)
    assert isinstance(error, ConfigurationError)
    assert isinstance(error, TrussiumError)
    assert isinstance(error, RuntimeError)
    assert error.capability_name == "chat.completions"
    assert error.code == "capability_already_registered"
    assert error.message == "Capability 'chat.completions' is already registered."
    assert registry.capabilities == (original,)


def test_constructor_rejects_duplicate_registration() -> None:
    """Initial registrations should enforce the same duplicate contract."""
    with pytest.raises(CapabilityAlreadyRegisteredError):
        CapabilityRegistry(
            (
                CapabilityRegistration("chat.completions", object()),
                CapabilityRegistration("chat.completions", object()),
            )
        )


def test_required_lookup_has_stable_typed_failure() -> None:
    """Missing required capabilities should expose bounded metadata."""
    registry = CapabilityRegistry()

    with pytest.raises(CapabilityNotFoundError) as captured:
        registry.require("chat.completions")

    error = captured.value
    assert isinstance(error, CapabilityRegistryError)
    assert isinstance(error, ConfigurationError)
    assert error.capability_name == "chat.completions"
    assert error.code == "capability_not_found"
    assert error.message == "Capability 'chat.completions' is not registered."

    with pytest.raises(CapabilityNotFoundError):
        registry.require_metadata("chat.completions")


@pytest.mark.parametrize("name", ["", "UPPER", "has space", "a" * 65])
def test_registration_and_lookup_share_name_validation(name: str) -> None:
    """Every named operation should preserve the same bounded identity contract."""
    registry = CapabilityRegistry()

    with pytest.raises(ValueError, match="must match"):
        CapabilityRegistration(name, object())
    with pytest.raises(ValueError, match="must match"):
        registry.register(name, object())
    with pytest.raises(ValueError, match="must match"):
        registry.get(name)
    with pytest.raises(ValueError, match="must match"):
        registry.require(name)


def test_none_registration_is_rejected_without_registry_mutation() -> None:
    """A missing implementation is a contract error rather than a capability."""
    registry = CapabilityRegistry()

    with pytest.raises(ValueError, match="must not be None"):
        registry.register("chat.completions", None)

    assert registry.registrations == ()


def test_metadata_name_mismatch_is_rejected_without_registry_mutation() -> None:
    """Public metadata must never describe a different registered implementation."""
    registry = CapabilityRegistry()

    with pytest.raises(ValueError, match="metadata name must match"):
        registry.register(
            "future.embeddings",
            object(),
            metadata=CapabilityMetadata(name="future.images"),
        )

    assert registry.registrations == ()
    assert registry.metadata == ()


def test_seal_is_idempotent_and_prevents_further_registration() -> None:
    """Composition should close mutation without changing discovery."""
    capability = object()
    registry = CapabilityRegistry((CapabilityRegistration("chat.completions", capability),))

    first_snapshot = registry.seal()
    second_snapshot = registry.seal()

    assert registry.sealed is True
    assert first_snapshot == second_snapshot == registry.registrations
    assert registry.get("chat.completions") is capability

    with pytest.raises(CapabilityRegistrySealedError) as captured:
        registry.register("later", object())

    error = captured.value
    assert isinstance(error, CapabilityRegistryError)
    assert isinstance(error, ConfigurationError)
    assert error.code == "capability_registry_sealed"
    assert error.message == "Capability registry is sealed."
    assert registry.capabilities == (capability,)


def test_contract_mismatch_error_is_bounded() -> None:
    """Known protocol mismatches should not expose registered object details."""
    error = CapabilityContractMismatchError("chat.completions")

    assert isinstance(error, CapabilityRegistryError)
    assert error.capability_name == "chat.completions"
    assert error.code == "capability_contract_mismatch"
    assert error.message == (
        "Capability 'chat.completions' does not implement its required contract."
    )
