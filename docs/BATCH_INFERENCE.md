# Batch inference

Trussium exposes provider-neutral lifecycle metadata for asynchronous batch jobs:

- `POST /v1/batches`
- `GET /v1/batches/{batch_id}`
- `POST /v1/batches/{batch_id}/cancel`

The initial OpenAI integration accepts only `/v1/chat/completions` batches with
a caller-owned provider `input_file_id`. Input and output files remain at the
provider: Trussium does not upload, download, persist, or log their contents.

Batch requests are for offline work and use the provider's fixed 24-hour
completion window. Arbitrary endpoint proxying, file uploads, result downloads,
webhooks, retries, and local scheduling are outside this capability.
