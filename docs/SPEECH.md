# Text-to-speech

Trussium exposes provider-neutral, non-streaming text-to-speech at
`POST /v1/audio/speech`. Applications register a `SpeechCapability`
implementation in the sealed capability registry.

Requests contain bounded text, model, voice, output format, and speed options.
Responses contain a base64-encoded audio artifact and provider metadata. Input
text, audio bytes, credentials, endpoints, and provider payloads are not logged.
