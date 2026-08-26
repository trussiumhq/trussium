"""Provider-neutral translation contracts."""

from trussium.capabilities.translation.capability import (
    TRANSLATION_CAPABILITY_METADATA,
    TRANSLATION_CAPABILITY_NAME,
    TranslationCapability,
)
from trussium.capabilities.translation.models import (
    TranslationRequest,
    TranslationResponse,
    TranslationResult,
)

__all__ = [
    "TRANSLATION_CAPABILITY_METADATA",
    "TRANSLATION_CAPABILITY_NAME",
    "TranslationCapability",
    "TranslationRequest",
    "TranslationResponse",
    "TranslationResult",
]
