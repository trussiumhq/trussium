# Audio-transcription capability

Trussium exposes provider-neutral, non-streaming audio transcription at
`POST /v1/audio/transcriptions`.

The endpoint receives multipart form data and forwards the audio directly to the
configured provider. Trussium does not persist the audio, transcript, credential,
endpoint, or provider payload. Structured logs receive only the normal request,
execution, capability, provider, and model context.

```bash
curl http://localhost:9000/v1/audio/transcriptions \
  -F model=gpt-4o-transcribe \
  -F language=en \
  -F file=@recording.wav
```

```json
{
  "id": "bfc37f15-ff22-4b57-a8f2-aa01ab9af121",
  "provider": "openai",
  "model": "gpt-4o-transcribe",
  "text": "Hello world",
  "language": "en",
  "duration": 1.2,
  "segments": [
    {"id": 0, "start": 0.0, "end": 1.2, "text": "Hello world"}
  ]
}
```

The initial capability supports direct single-request transcription and normalized
segment metadata when supplied by the provider. Streaming transcription,
translation, diarization, audio storage, asynchronous jobs, routing, retries, and
fallback remain separate concerns.
