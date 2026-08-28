"""Trussium provider adapters and provider-neutral contracts."""

from trussium.providers.circuit_breaker import CircuitBreaker
from trussium.providers.contracts import Provider, ProviderMetadata, validate_provider_name
from trussium.providers.health import (
    ProviderHealth,
    ProviderHealthCheck,
    ProviderHealthReport,
    ProviderHealthReporter,
    ProviderHealthStatus,
)
from trussium.providers.lifecycle import ProviderLifecycle, ProviderService
from trussium.providers.models import ProviderModel, ProviderModelDiscovery, validate_model_id
from trussium.providers.plugins import (
    PLUGIN_API_VERSION,
    PLUGIN_PERMISSIONS,
    ProviderPluginCompatibilityError,
    ProviderPluginError,
    ProviderPluginLoader,
    ProviderPluginLoadError,
    ProviderPluginNotFoundError,
    ProviderPluginPermissionError,
    ProviderPluginSpec,
)
from trussium.providers.registry import (
    ProviderAlreadyRegisteredError,
    ProviderContractMismatchError,
    ProviderNotFoundError,
    ProviderRegistry,
    ProviderRegistryError,
    ProviderRegistrySealedError,
)
from trussium.providers.retry import (
    ProviderFailureClass,
    RetryDecision,
    RetryPolicy,
    classify_failure,
)
from trussium.providers.routing import ProviderRouter, RoutingDecision

__all__ = [
    "PLUGIN_API_VERSION",
    "PLUGIN_PERMISSIONS",
    "CircuitBreaker",
    "Provider",
    "ProviderAlreadyRegisteredError",
    "ProviderContractMismatchError",
    "ProviderFailureClass",
    "ProviderHealth",
    "ProviderHealthCheck",
    "ProviderHealthReport",
    "ProviderHealthReporter",
    "ProviderHealthStatus",
    "ProviderLifecycle",
    "ProviderMetadata",
    "ProviderModel",
    "ProviderModelDiscovery",
    "ProviderNotFoundError",
    "ProviderPluginCompatibilityError",
    "ProviderPluginError",
    "ProviderPluginLoadError",
    "ProviderPluginLoader",
    "ProviderPluginNotFoundError",
    "ProviderPluginPermissionError",
    "ProviderPluginSpec",
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderRegistrySealedError",
    "ProviderRouter",
    "ProviderService",
    "RetryDecision",
    "RetryPolicy",
    "RoutingDecision",
    "classify_failure",
    "validate_model_id",
    "validate_provider_name",
]
