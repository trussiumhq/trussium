# TypeScript SDK

The TypeScript SDK is maintained in the dedicated
[`trussium-typescript`](https://github.com/trussiumhq/trussium-typescript)
repository and published as `@trussium/sdk` when npm publication is enabled.
It calls an existing local, private, or public runtime; it does not install,
host, or configure one.

```bash
git clone https://github.com/trussiumhq/trussium-typescript.git
cd trussium-typescript
npm ci
npm run build
```

```ts
import { TrussiumClient } from "@trussium/sdk";

const client = new TrussiumClient({ baseUrl: "http://127.0.0.1:9000" });
const response = await client.complete(
  { model: "gpt-4.1-mini", messages: [{ role: "user", content: "Hello" }] },
  "request-123",
);

const translation = await client.translate(
  {
    model: "translator",
    input: ["Hello world"],
    source_language: "en",
    target_language: "fr",
  },
  "translation-123",
);
```

Version `v1.2.0` provides typed non-streaming chat completions, readiness,
capability discovery, embeddings, moderation, image generation, multipart
transcription, reranking, translation, batch jobs, video jobs, controlled tools,
request-ID forwarding, and typed API errors. Semantic release currently creates versions,
tags, changelogs, and GitHub releases; npm publication is deferred until the
repository has an `NPM_TOKEN`. See the dedicated repository for package and
runtime compatibility details.

## Runnable example

The dedicated repository includes [`examples/basic.ts`](https://github.com/trussiumhq/trussium-typescript/blob/main/examples/basic.ts),
which checks readiness, discovers capabilities, and submits a chat request.
Build it with `npm run build:examples` and configure `TRUSSIUM_URL`,
`TRUSSIUM_MODEL`, and `TRUSSIUM_PROMPT`; it defaults to the local runtime at
`http://127.0.0.1:9000`.
