# Image-generation capability

Trussium exposes provider-neutral, non-streaming image generation at `POST /v1/images/generations`.

```json
{"model":"gpt-image-1","prompt":"a mountain sunrise"}
```

The runtime must have an image capability registered and a provider configured
before this request can succeed. A copyable request is:

```bash
curl -sS http://127.0.0.1:9000/v1/images/generations \
  -H 'content-type: application/json' \
  -d '{"model":"gpt-image-1","prompt":"a mountain sunrise","count":1}'
```

Responses contain base64 image artifacts and no hosted URLs. Prompts, image data, credentials, endpoints, and provider payloads remain outside structured logs. Image storage, serving, editing, uploads, and asynchronous jobs are out of scope.

If the capability is not registered, the endpoint returns `503
image_generation_capability_unavailable`; invalid or unsupported request fields return
`400`/`422`. Provider authentication, quota, model availability, and content
policy failures remain provider-specific and are reported as bounded runtime
errors. The runtime does not retry or store generated image bytes.
