# Model aliasing

Trussium can expose stable client-facing model names while allowing operators
to change the concrete provider model through runtime configuration.

Configure a bounded JSON object with `TRUSSIUM_RUNTIME__MODEL_ALIASES`:

```text
TRUSSIUM_RUNTIME__MODEL_ALIASES={"fast":"provider-model-v2"}
```

Requests may use `fast`; the runtime resolves it to `provider-model-v2` before
provider execution. Responses, streaming start events, execution context, and
provider logs use the resolved model so operational records identify what ran.
Requests using an unmapped model are unchanged.

Aliases are declaration-time configuration only. They do not probe providers,
select among models, or hide provider errors. The map supports at most 64
lowercase aliases, and each target is a non-empty, stripped identifier of at
most 128 characters. Credentials, endpoints, and request payloads are never
part of alias configuration or logs.
