import pytest
from pydantic import ValidationError

from trussium.capabilities.translation import TranslationRequest, TranslationResult


def test_translation_request_is_immutable_and_validated() -> None:
    request = TranslationRequest(
        model="translator",
        input=["Hello"],
        source_language="en",
        target_language="fr",
    )

    with pytest.raises(ValidationError):
        request.model = "other"  # type: ignore[misc]


def test_translation_result_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        TranslationResult(text="", target_language="fr")
