# Image-generation capability

Trussium exposes provider-neutral, non-streaming image generation at `POST /v1/images/generations`.

```json
{"model":"gpt-image-1","prompt":"a mountain sunrise"}
```

Responses contain base64 image artifacts and no hosted URLs. Prompts, image data, credentials, endpoints, and provider payloads remain outside structured logs. Image storage, serving, editing, uploads, and asynchronous jobs are out of scope.
