# Text-to-speech

Trussium exposes provider-neutral, non-streaming text-to-speech at
`POST /v1/audio/speech`. Applications register a `SpeechCapability`
implementation in the sealed capability registry.

Requests contain bounded text, model, voice, output format, and speed options.
Responses contain a base64-encoded audio artifact and provider metadata. Input
text, audio bytes, credentials, endpoints, and provider payloads are not logged.

## Self-hosted Piper

For self-hosted text-to-speech, install the independently versioned
[`trussium-provider-piper`](https://github.com/trussiumhq/trussium-provider-piper)
package and register `PiperSpeechCapability` in the application. Configure its
`base_url` to the separately operated Piper HTTP service, for example
`http://piper:5000`. The adapter sends text, voice, and speed to Piper and
normalizes the returned audio to the runtime's base64-encoded WAV response. It
does not install, configure, or manage Piper, and non-WAV output is rejected.
