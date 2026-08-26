import pytest
from pydantic import ValidationError

from trussium.capabilities.speech import SpeechRequest


def test_speech_request_is_immutable_and_bounded() -> None:
    request = SpeechRequest(model="voice-model", input="Hello", voice="alloy")
    with pytest.raises(ValidationError):
        request.speed = 9.0


def test_speech_request_rejects_unsupported_format() -> None:
    with pytest.raises(ValidationError):
        SpeechRequest(model="voice-model", input="Hello", voice="alloy", response_format="ogg")
