"""Provider-neutral Trussium capabilities."""

from trussium.capabilities.chat import CHAT_CAPABILITY_METADATA, CHAT_CAPABILITY_NAME
from trussium.capabilities.metadata import CapabilityMetadata
from trussium.capabilities.registry import (
    CapabilityAlreadyRegisteredError,
    CapabilityContractMismatchError,
    CapabilityNotFoundError,
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityRegistryError,
    CapabilityRegistrySealedError,
    validate_capability_name,
)

__all__ = [
    "CHAT_CAPABILITY_METADATA",
    "CHAT_CAPABILITY_NAME",
    "CapabilityAlreadyRegisteredError",
    "CapabilityContractMismatchError",
    "CapabilityMetadata",
    "CapabilityNotFoundError",
    "CapabilityRegistration",
    "CapabilityRegistry",
    "CapabilityRegistryError",
    "CapabilityRegistrySealedError",
    "validate_capability_name",
]
