# Translation

Trussium exposes provider-neutral, non-streaming text translation at
`POST /v1/translations`.

Applications register a `TranslationCapability` implementation in the sealed
capability registry. The execution pipeline propagates request, execution,
capability, provider, and model context.

Translation text, credentials, endpoints, and provider payloads are not
written to structured logs.
