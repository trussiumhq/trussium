"""Bounded provider-neutral metadata for public capability discovery."""

import re
from dataclasses import dataclass
from typing import Final

_CAPABILITY_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_CAPABILITY_VERSION_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9._-]{0,31}")
_MAX_DESCRIPTION_LENGTH: Final = 160


def validate_capability_name(name: str) -> str:
    """Return a bounded capability name or raise ``ValueError``."""
    if _CAPABILITY_NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("Capability name must match [a-z][a-z0-9_.-]{0,63}")

    return name


@dataclass(frozen=True, slots=True)
class CapabilityMetadata:
    """Immutable public description of one provider-neutral capability contract."""

    name: str
    version: str | None = None
    description: str | None = None
    supports_streaming: bool | None = None

    def __post_init__(self) -> None:
        """Validate bounded public metadata without provider or implementation data."""
        validate_capability_name(self.name)

        if self.version is not None and _CAPABILITY_VERSION_PATTERN.fullmatch(self.version) is None:
            raise ValueError("Capability metadata version must match [a-z0-9][a-z0-9._-]{0,31}")

        if self.description is not None and (
            not self.description
            or self.description != self.description.strip()
            or len(self.description) > _MAX_DESCRIPTION_LENGTH
            or any(ord(character) < 32 or ord(character) == 127 for character in self.description)
        ):
            raise ValueError(
                "Capability metadata description must be stripped, contain no control "
                "characters, and contain 1 to 160 characters"
            )

        if self.supports_streaming is not None and not isinstance(self.supports_streaming, bool):
            raise ValueError("Capability metadata supports_streaming must be a boolean")


__all__ = ["CapabilityMetadata", "validate_capability_name"]
