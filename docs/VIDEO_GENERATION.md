# Video-generation jobs

Trussium creates and retrieves provider-neutral video-job metadata at `POST /v1/videos` and `GET /v1/videos/{video_id}`.

The initial adapter uses OpenAI video jobs. Trussium returns only job metadata; it does not download, store, serve, or log video bytes, prompts, credentials, endpoints, or provider payloads.

The capability must be registered and the provider configured before creating a
job. Creation is asynchronous; poll the returned identifier rather than
expecting video bytes in the create response:

```bash
curl -sS http://127.0.0.1:9000/v1/videos \
  -H 'content-type: application/json' \
  -d '{"model":"sora-2","prompt":"A sunrise over the ocean","seconds":"4","size":"1280x720"}'
curl -sS http://127.0.0.1:9000/v1/videos/<video-id>
```

An unregistered capability returns `503 video_capability_unavailable`; invalid duration or
size values return `400`/`422`. Provider job expiry, quota, and model access
remain provider-specific. Trussium does not retry jobs or host their resulting
media.
