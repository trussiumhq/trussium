# Video-generation jobs

Trussium creates and retrieves provider-neutral video-job metadata at `POST /v1/videos` and `GET /v1/videos/{video_id}`.

The initial adapter uses OpenAI video jobs. Trussium returns only job metadata; it does not download, store, serve, or log video bytes, prompts, credentials, endpoints, or provider payloads.
