"""Trussium cloud-native AI runtime platform."""

from collections.abc import Callable
from importlib import metadata

from trussium.errors import (
    CapabilityError,
    ConfigurationError,
    DependencyError,
    LifecycleError,
    ProviderError,
    RuntimeExecutionError,
    TrussiumError,
)

_UNKNOWN_VERSION = "0.0.0+unknown"


def _get_version(version_reader: Callable[[str], str] = metadata.version) -> str:
    """Return installed distribution metadata or a source-tree fallback."""
    try:
        return version_reader("trussium")
    except metadata.PackageNotFoundError:
        return _UNKNOWN_VERSION


__version__ = _get_version()

__all__ = [
    "CapabilityError",
    "ConfigurationError",
    "DependencyError",
    "LifecycleError",
    "ProviderError",
    "RuntimeExecutionError",
    "TrussiumError",
    "__version__",
]
