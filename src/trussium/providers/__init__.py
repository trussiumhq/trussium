"""Trussium provider adapters and provider-neutral contracts."""

from trussium.providers.contracts import Provider, ProviderMetadata, validate_provider_name
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
    "ProviderMetadata",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderRegistrySealedError",
    "validate_provider_name",
]
