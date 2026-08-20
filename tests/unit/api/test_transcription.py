"""Tests for the provider-neutral audio-transcription endpoint."""

from fastapi import status
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    TRANSCRIPTION_CAPABILITY_METADATA,
    TRANSCRIPTION_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.capabilities.transcription import TranscriptionRequest, TranscriptionResponse


class StubTranscriptionCapability:
    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse:
        assert request.audio.data == b"audio-data"
        return TranscriptionResponse(
            id="transcription-test-1",
            provider="stub",
            model=request.model,
            text="Hello world",
            language=request.language,
        )


def test_transcription_returns_normalized_response() -> None:
    registry = CapabilityRegistry()
    registry.register(
        TRANSCRIPTION_CAPABILITY_NAME,
        StubTranscriptionCapability(),
        metadata=TRANSCRIPTION_CAPABILITY_METADATA,
    )
    response = TestClient(create_application(capability_registry=registry)).post(
        "/v1/audio/transcriptions",
        data={"model": "gpt-4o-transcribe", "language": "en"},
        files={"file": ("sample.wav", b"audio-data", "audio/wav")},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": "transcription-test-1",
        "provider": "stub",
        "model": "gpt-4o-transcribe",
        "text": "Hello world",
        "language": "en",
        "duration": None,
        "segments": [],
    }


def test_transcription_without_registered_capability_is_unavailable() -> None:
    response = TestClient(create_application()).post(
        "/v1/audio/transcriptions",
        data={"model": "gpt-4o-transcribe"},
        files={"file": ("sample.wav", b"audio-data", "audio/wav")},
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"]["code"] == "transcription_capability_unavailable"
