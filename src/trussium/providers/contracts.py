"""Provider-neutral provider interface and metadata contracts."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from trussium.capabilities.metadata import validate_capability_name

_PROVIDER_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_PROVIDER_VERSION_PATTERN: Final = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._+-]{0,31}")
_MAX_DESCRIPTION_LENGTH: Final = 160
_MAX_CAPABILITIES: Final = 64


def validate_provider_name(name: str) -> str:
    """Return a bounded provider name or raise ``ValueError``."""
    if _PROVIDER_NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("Provider name must match [a-z][a-z0-9_.-]{0,63}")
    return name


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Immutable, bounded public metadata describing one provider."""

    name: str
    version: str
    capabilities: tuple[str, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate metadata before it can cross a discovery boundary."""
        validate_provider_name(self.name)
        if _PROVIDER_VERSION_PATTERN.fullmatch(self.version) is None:
            raise ValueError(
                "Provider metadata version must match [a-zA-Z0-9][a-zA-Z0-9._+-]{0,31}"
            )
        if not isinstance(self.capabilities, tuple):
            raise ValueError("Provider metadata capabilities must be a tuple")
        if len(self.capabilities) > _MAX_CAPABILITIES:
            raise ValueError("Provider metadata supports at most 64 capabilities")
        normalized = tuple(validate_capability_name(name) for name in self.capabilities)
        if len(set(normalized)) != len(normalized):
            raise ValueError("Provider metadata capabilities must be unique")
        if normalized != self.capabilities:
            object.__setattr__(self, "capabilities", normalized)
        if self.description is not None and (
            not self.description
            or self.description != self.description.strip()
            or len(self.description) > _MAX_DESCRIPTION_LENGTH
            or any(ord(character) < 32 or ord(character) == 127 for character in self.description)
        ):
            raise ValueError(
                "Provider metadata description must be stripped, contain no control "
                "characters, and contain 1 to 160 characters"
            )


@runtime_checkable
class Provider(Protocol):
    """Interface implemented by an application-owned provider adapter."""

    @property
    def metadata(self) -> ProviderMetadata:
        """Return immutable public provider metadata."""
        ...

    @property
    def capabilities(self) -> Sequence[object]:
        """Return capability adapter instances in stable order."""
        ...


__all__ = ["Provider", "ProviderMetadata", "validate_provider_name"]
