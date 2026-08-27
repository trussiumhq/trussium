"""Provider-neutral model metadata and optional discovery contract."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from trussium.providers.contracts import Provider

_MODEL_ID_PATTERN: Final = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}")
_MAX_MODELS: Final = 256


def validate_model_id(model_id: str) -> str:
    """Return a bounded model identifier or raise ``ValueError``."""
    if _MODEL_ID_PATTERN.fullmatch(model_id) is None:
        raise ValueError("Model identifiers must be bounded printable provider identifiers")
    return model_id


@dataclass(frozen=True, slots=True)
class ProviderModel:
    """Immutable public metadata for one provider model."""

    id: str
    owned_by: str | None = None

    def __post_init__(self) -> None:
        validate_model_id(self.id)
        if self.owned_by is not None:
            validate_model_id(self.owned_by)


@runtime_checkable
class ProviderModelDiscovery(Provider, Protocol):
    """Optional provider contract for bounded model metadata discovery."""

    async def list_models(self) -> Sequence[ProviderModel]:
        """Return provider models without executing inference."""
        ...


__all__ = [
    "ProviderModel",
    "ProviderModelDiscovery",
    "validate_model_id",
]
