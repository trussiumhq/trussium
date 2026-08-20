# Reranking capability

Trussium exposes provider-neutral reranking at `POST /v1/rerankings`.

```json
{"model":"bge-reranker","query":"refund policy","documents":[{"text":"Refunds are available for 30 days."}]}
```

The initial adapter targets privately hosted Hugging Face Text Embeddings Inference
(TEI) at its `/rerank` endpoint. Configure `TRUSSIUM_RERANKING__BASE_URL` for
the TEI server and optionally `TRUSSIUM_RERANKING__API_KEY`.

Trussium does not retrieve, store, or log query/document text, credentials,
provider endpoints, or provider payloads. Retrieval, indexing, routing, retries,
batching, and streaming are separate concerns.
