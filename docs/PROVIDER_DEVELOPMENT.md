# Provider Development Guide

Provider adapters translate an upstream provider API into Trussium's
provider-neutral capability contracts. An adapter owns upstream request
translation and response normalization; the runtime owns HTTP, execution
context, timeouts, lifecycle, health reporting, and structured operational
logging.

This guide describes the current in-repository extension boundary. Provider
registries, dynamic plugin loading, and automatic model discovery are future
work and are not required to add a test-backed adapter today.

The first standalone community adapter is
[`trussium-provider-vllm`](https://github.com/trussiumhq/trussium-provider-vllm).
It connects to a separately operated self-hosted vLLM deployment through its
OpenAI-compatible chat API. Install and register it explicitly in the
application; the plugin does not install, configure, or manage vLLM.

The first managed-provider adapter is
[`trussium-provider-anthropic`](https://github.com/trussiumhq/trussium-provider-anthropic).
It translates Anthropic's Messages API and SSE lifecycle into the same
normalized chat contract. Supply its API key through the application's secret
boundary and register it explicitly; the plugin does not store credentials or
manage the Anthropic service.

The first standalone translation adapter is
[`trussium-provider-libretranslate`](https://github.com/trussiumhq/trussium-provider-libretranslate).
It connects to a separately operated LibreTranslate deployment and implements
the `TranslationCapability`; it does not host or manage LibreTranslate.

The first standalone speech adapter is
[`trussium-provider-piper`](https://github.com/trussiumhq/trussium-provider-piper).
It connects to a separately operated Piper HTTP service and implements the
`SpeechCapability`; it supports WAV output and does not install or manage Piper.

## Choose a capability contract

Start with the provider-neutral protocol for the capability you are adding:

| Capability | Contract | Streaming |
| --- | --- | --- |
| Chat | [`ChatCapability`](../src/trussium/capabilities/chat/capability.py) | Yes |
| Embeddings | [`EmbeddingsCapability`](../src/trussium/capabilities/embeddings/capability.py) | No |
| Images | [`ImageGenerationCapability`](../src/trussium/capabilities/images/capability.py) | No |
| Moderation | [`ModerationCapability`](../src/trussium/capabilities/moderation/capability.py) | No |
| Reranking | [`RerankingCapability`](../src/trussium/capabilities/reranking/capability.py) | No |
| Translation | [`TranslationCapability`](../src/trussium/capabilities/translation/capability.py) | No |
| Transcription | [`TranscriptionCapability`](../src/trussium/capabilities/transcription/capability.py) | No |
| Speech | [`SpeechCapability`](../src/trussium/capabilities/speech/capability.py) | No |
| Video jobs | [`VideoCapability`](../src/trussium/capabilities/videos/capability.py) | No |

Implement the protocol's normalized request and response types. Do not expose
an upstream SDK type, provider response object, or provider-specific option
through the public capability contract.

## Adapter responsibilities

An adapter should:

1. Translate the normalized request into the upstream request.
2. Preserve the requested model and relevant bounded metadata.
3. Normalize successful responses into the capability response model.
4. Normalize provider failures into `CapabilityExecutionError` or a bounded
   `ProviderError` with a stable snake-case code and safe message.
5. Normalize streaming events in order and close the upstream iterator on
   completion, cancellation, timeout, and consumer disconnect.
6. Expose a bounded `provider_name` used by response metadata and logs.

An adapter must not log prompts, response bodies, credentials, raw provider
exceptions, or unbounded provider metadata. Preserve native cancellation and
unexpected programming errors rather than converting them into a provider
failure.

## Configuration and composition

Add typed settings only when the provider needs configuration that cannot use
the existing provider boundary. Provider credentials and URLs are injected
through environment variables or a secret store; never commit them.

The current composition path is explicit in
[`app/bootstrap.py`](../src/trussium/app/bootstrap.py): construct the adapter,
wrap it with runtime-owned timeout and observability boundaries, and register
the provider-neutral capability in the application registry. Keep provider
selection out of API route handlers.

OpenAI-compatible adapters use the existing `ProviderSettings` fields:

```bash
TRUSSIUM_PROVIDER__NAME=openai
TRUSSIUM_PROVIDER__BASE_URL=https://provider.example/v1
TRUSSIUM_PROVIDER__API_KEY=replace-with-a-secret
```

Ollama uses the same normalized Responses API boundary with a private default
URL:

```bash
TRUSSIUM_PROVIDER__NAME=ollama
TRUSSIUM_PROVIDER__BASE_URL=http://127.0.0.1:11434/v1
```

## Deadlines, health, and availability

The runtime owns provider request and stream-idle deadlines. Do not add a
second competing deadline in an adapter unless the upstream SDK requires a
transport timeout; the runtime deadline remains authoritative.

Provider dependency checks are opt-in and bounded. A health check should make a
small metadata request, respect the configured deadline, and return a stable
failure reason without making inference or downloading a model. Health and
capability availability are informational contracts; they must not change
liveness or silently gate execution.

## Error mapping

Use the categories in
[`capabilities/errors.py`](../src/trussium/capabilities/errors.py):

| Condition | Category |
| --- | --- |
| Invalid caller payload | `INVALID_REQUEST` |
| Provider rate limit | `RATE_LIMITED` |
| Provider quota exhausted | `QUOTA_EXCEEDED` |
| Invalid or missing credential | `UPSTREAM_AUTHENTICATION` |
| Provider permission denial | `UPSTREAM_PERMISSION` |
| Upstream deadline | `UPSTREAM_TIMEOUT` |
| Connection or DNS failure | `UPSTREAM_CONNECTION` |
| Other provider failure or malformed response | `UPSTREAM_FAILURE` |

Codes must describe durable conditions, for example
`ollama_provider_timeout`, not an upstream request ID or raw message. Follow
the public exception and cancellation boundaries in [ERRORS.md](ERRORS.md).

## Testing checklist

Every adapter should have deterministic tests with a fake transport or local
fake provider. Cover:

- normalized request serialization;
- successful JSON response normalization;
- every relevant upstream error category and safe message;
- malformed and incomplete responses;
- streaming start, delta, end, error, cancellation, and iterator cleanup;
- provider and model metadata;
- bounded health behavior when the provider is unavailable.

Run the standard checks before opening a PR:

```bash
uv run ruff check src tests
uv run ruff format --check .
uv run mypy src tests
uv run pytest tests/unit/providers
uv run pytest
```

Use the opt-in live Ollama suite only when a compatible local model is already
available. Tests must never download models or require external credentials.

## Review checklist

- [ ] The adapter implements an existing provider-neutral capability protocol.
- [ ] Upstream types do not cross the capability boundary.
- [ ] Errors have stable codes, safe messages, and correct categories.
- [ ] Cancellation, deadlines, and streaming cleanup are preserved.
- [ ] Provider credentials and payloads are absent from logs and tests.
- [ ] Composition is explicit and documented.
- [ ] Unit, formatting, type, and integration checks pass.

The provider framework remains intentionally explicit until the future provider
registry and plugin-development milestones define a stable loading contract.
