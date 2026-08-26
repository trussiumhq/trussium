"""Trussium provider adapters and provider-neutral contracts."""

from trussium.providers.contracts import Provider, ProviderMetadata, validate_provider_name
from trussium.providers.lifecycle import ProviderLifecycle, ProviderService
from trussium.providers.registry import (
    ProviderAlreadyRegisteredError,
    ProviderContractMismatchError,
    ProviderNotFoundError,
    ProviderRegistry,
    ProviderRegistryError,
    ProviderRegistrySealedError,
)

__all__ = [
    "Provider",
    "ProviderAlreadyRegisteredError",
    "ProviderContractMismatchError",
    "ProviderLifecycle",
    "ProviderMetadata",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderRegistrySealedError",
    "ProviderService",
    "validate_provider_name",
]
