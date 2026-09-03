# Translation

Trussium exposes provider-neutral, non-streaming text translation at
`POST /v1/translations`.

Applications register a `TranslationCapability` implementation in the sealed
capability registry. The execution pipeline propagates request, execution,
capability, provider, and model context.

Translation text, credentials, endpoints, and provider payloads are not
written to structured logs.

## Request example and prerequisites

Register a translation capability and configure its provider before sending a
request. The normalized contract accepts one or more input strings and a target
language:

```bash
curl -sS http://127.0.0.1:9000/v1/translations \
  -H 'content-type: application/json' \
  -d '{"model":"translator","input":["Hello world"],"source_language":"en","target_language":"fr"}'
```

An unregistered capability returns `503 translation_capability_unavailable`; malformed
language codes or missing input return `400`/`422`. Provider credentials,
language support, quotas, and translation quality are provider concerns. The
runtime does not infer missing providers, retry failures, or persist source or
translated text.
