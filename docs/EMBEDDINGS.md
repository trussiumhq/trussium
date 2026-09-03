# Embeddings capability

Trussium exposes provider-neutral, non-streaming text embeddings at `POST /v1/embeddings`.

```json
{"model":"text-embedding-3-small","input":["first document","second document"]}
```

The response contains the provider, resolved model, vectors in input order, and input-token usage. It never logs request text, vectors, credentials, provider endpoints, or configuration values. The endpoint uses the same sealed capability registry and execution context as chat, so normal request, execution, capability, provider, and model correlation applies.

Embeddings do not add a vector database, retrieval, chunking, RAG orchestration, batching, routing, retries, fallback, model discovery, or execution gating. Existing chat and streaming contracts are unchanged.

The embeddings capability must be registered and its provider configured before
calling the endpoint. A `503 embeddings_capability_unavailable` response means the
capability is not available; `400`/`422` responses indicate invalid input. A
provider may also reject an unsupported model or exceed its quota. The runtime
does not persist vectors or provide a vector index, so callers must store and
secure returned vectors themselves.
