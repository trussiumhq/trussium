# CHANGELOG

<!-- version list -->

## v0.28.0 (2026-08-12)

### Features

- **observability**: Add structured operational logs
  ([`d0dd218`](https://github.com/trussiumhq/trussium/commit/d0dd21827d47637baaebfe39cf4c09608d04f861))


## v0.27.0 (2026-08-12)

### Documentation

- Align Helm v0.3.0 release references
  ([`06a5f68`](https://github.com/trussiumhq/trussium/commit/06a5f6843c09529b53c10169c45c4871c18ee691))

### Features

- **observability**: Add distributed tracing
  ([`28a4355`](https://github.com/trussiumhq/trussium/commit/28a43555fe2d2dde0b7a8fb34456adf514a79a77))


## v0.26.0 (2026-08-11)

### Documentation

- Document Helm v0.2 autoscaling release
  ([`7c045db`](https://github.com/trussiumhq/trussium/commit/7c045db8b99aa0b913292ffeb31fa0eb6beb3d4a))

### Features

- **observability**: Add OpenTelemetry instrumentation
  ([`6671eff`](https://github.com/trussiumhq/trussium/commit/6671effc589acccc61ffa6a93eeb04299532fe3b))


## v0.25.0 (2026-08-11)

### Documentation

- Document official Helm chart release
  ([`18ac523`](https://github.com/trussiumhq/trussium/commit/18ac523068c35658b841efaa6c959d2557b93a4b))

### Features

- **observability**: Add runtime metrics and autoscaling
  ([`da942f9`](https://github.com/trussiumhq/trussium/commit/da942f93079e48a306cbb98f0ca1d0d01c44dcba))


## v0.24.0 (2026-08-05)

### Features

- **kubernetes**: Add production manifests
  ([`ec60909`](https://github.com/trussiumhq/trussium/commit/ec60909cd761ce00a96e1c3369f927e3af9d4781))


## v0.23.0 (2026-08-05)

### Features

- **runtime**: Validate graceful shutdown
  ([`e16d0fe`](https://github.com/trussiumhq/trussium/commit/e16d0fec299a9e2553f48e04a8dc415fbd59c81b))


## v0.22.0 (2026-08-05)

### Features

- **packaging**: Validate distribution artifacts
  ([`1627a0d`](https://github.com/trussiumhq/trussium/commit/1627a0dbca4e78d3b0a63a40aa27dfd3d5e11a44))


## v0.21.1 (2026-08-05)

### Bug Fixes

- **container**: Dispatch publication after release
  ([`acd6d16`](https://github.com/trussiumhq/trussium/commit/acd6d162a477b4b5e0767ccf7c000b8adf431713))


## v0.21.0 (2026-08-05)

### Features

- **container**: Add production image packaging
  ([`ea05644`](https://github.com/trussiumhq/trussium/commit/ea0564479494fdf1380e1293ab882dddb0755c66))


## v0.20.0 (2026-08-05)

### Features

- **provider**: Validate Ollama compatibility
  ([`ea4832d`](https://github.com/trussiumhq/trussium/commit/ea4832ded5233f93053f65af2d1ebef747554467))


## v0.19.0 (2026-08-05)

### Features

- **testing**: Add end-to-end runtime suite
  ([`d21cb0e`](https://github.com/trussiumhq/trussium/commit/d21cb0e58944fb6b5b9013b39c7c70d12bbf0ab6))


## v0.18.0 (2026-08-05)

### Features

- **runtime**: Enforce provider timeouts
  ([`1569395`](https://github.com/trussiumhq/trussium/commit/1569395f99e15cff36153272624ee88f140df66d))


## v0.17.0 (2026-08-05)

### Features

- **runtime**: Handle client disconnects
  ([`1a6484a`](https://github.com/trussiumhq/trussium/commit/1a6484ab03090a7c642d3ce166cf0687f45312fd))


## v0.16.0 (2026-08-05)

### Features

- **observability**: Add provider execution logging
  ([`c30ea88`](https://github.com/trussiumhq/trussium/commit/c30ea886a24fea5631d8c5d6acd509644cbef4f3))


## v0.15.0 (2026-08-05)

### Features

- **observability**: Add capability execution logging
  ([`155757b`](https://github.com/trussiumhq/trussium/commit/155757b9adaf024098dcb21480e63b968c9f2280))


## v0.14.0 (2026-08-05)

### Features

- **runtime**: Add execution context propagation
  ([`720f95d`](https://github.com/trussiumhq/trussium/commit/720f95dccc279df152c1de864378334dc4bc8247))


## v0.13.0 (2026-08-04)

### Features

- **observability**: Add structured request logging
  ([`2cb9749`](https://github.com/trussiumhq/trussium/commit/2cb9749de4030ba7d69585f963724a4fc8d9f159))


## v0.12.0 (2026-08-04)

### Features

- **runtime**: Add request correlation IDs
  ([`b1fa7a8`](https://github.com/trussiumhq/trussium/commit/b1fa7a893f888e21ea51b26195c58dc6b8bbba68))


## v0.11.0 (2026-07-28)

### Features

- **api**: Normalize non-streaming provider errors
  ([`9726bb9`](https://github.com/trussiumhq/trussium/commit/9726bb9f50830595e9fe91712c9efb2cddb0fb5f))


## v0.10.0 (2026-07-24)

### Features

- **api**: Stream chat completions over SSE
  ([`6fcfb1a`](https://github.com/trussiumhq/trussium/commit/6fcfb1afcdcc48f1829381f21a35cb611d35cdf1))


## v0.9.0 (2026-07-23)

### Bug Fixes

- **test**: Fix formatting
  ([`ebc8e49`](https://github.com/trussiumhq/trussium/commit/ebc8e497f07aa8a5e7ca1fea6e0a3e2cda62ddc7))

### Features

- **api**: Expose chat completion endpoint
  ([`f0316d1`](https://github.com/trussiumhq/trussium/commit/f0316d15a3ca15ff717f739f056b21a7023d8c65))


## v0.8.0 (2026-07-23)

### Features

- **openai**: Implement chat capability adapter
  ([`51fe14e`](https://github.com/trussiumhq/trussium/commit/51fe14e4b944a6a70a01e6978552e95cd7dab854))


## v0.7.0 (2026-07-23)

### Features

- **chat**: Define capability provider interface
  ([`5f1b498`](https://github.com/trussiumhq/trussium/commit/5f1b49804e0f0df5f49abcfbdcff96b5649822fe))


## v0.6.0 (2026-07-23)

### Features

- **chat**: Add normalized completion contracts
  ([`079e232`](https://github.com/trussiumhq/trussium/commit/079e2324aa0c0206f2ed9ceb59c6ea15b307b1cc))


## v0.5.0 (2026-07-23)

### Bug Fixes

- **test**: Modify ddefault port from 8080 to 9000
  ([`8ab6b3f`](https://github.com/trussiumhq/trussium/commit/8ab6b3fcb34a798d1591a9bca272a22e06bf1a32))

### Features

- **api**: Add health check endpoints
  ([`d8624e3`](https://github.com/trussiumhq/trussium/commit/d8624e3e258de4f2181439ce9aa0fc354faa7341))


## v0.4.0 (2026-07-23)

### Features

- **app**: Implement application composition root
  ([`9aa843f`](https://github.com/trussiumhq/trussium/commit/9aa843fe74998bfe6dd8bd1d776f7de55e629925))


## v0.3.0 (2026-07-23)

### Features

- **config**: Implement application settings
  ([`21ffefc`](https://github.com/trussiumhq/trussium/commit/21ffefcce90b2504c41f4209a6eb65e2c812d976))


## v0.2.0 (2026-07-23)

### Documentation

- **adr**: Define runtime bootstrap architecture
  ([`1370f20`](https://github.com/trussiumhq/trussium/commit/1370f2028ed798bc0e865be1ef8bafc5c5ac790c))

### Features

- **runtime**: Bootstrap package structure
  ([`c960beb`](https://github.com/trussiumhq/trussium/commit/c960beb830c70129fa73a03172d2531686926b54))


## v0.1.3 (2026-07-23)

### Bug Fixes

- **ci**: Modify GH_TOKEN to test semantic versioning
  ([`1feafd7`](https://github.com/trussiumhq/trussium/commit/1feafd735a583b44866396cd6d2fed9002319b91))


## v0.1.2 (2026-07-23)

### Bug Fixes

- **ci**: Test semantic release automation
  ([`0823f66`](https://github.com/trussiumhq/trussium/commit/0823f66b5fa51987e2a2b64ca3b6076b9933899b))

- **ci**: Test semantic release automation
  ([`64efa29`](https://github.com/trussiumhq/trussium/commit/64efa2960eda71c8d8196f7d66539be40e980605))


## v0.1.1 (2026-07-23)

### Bug Fixes

- **ci**: Test semantic release automation
  ([`2824172`](https://github.com/trussiumhq/trussium/commit/282417229a27b67b86fc349b006232688bce9b5d))

- **ci**: Verify semantic release pipeline
  ([`9d06250`](https://github.com/trussiumhq/trussium/commit/9d062508a93cb30a100385e4f96550ee90bce9d0))

- **release**: Allow zero-version releases
  ([`197a61a`](https://github.com/trussiumhq/trussium/commit/197a61a9ff4d1b3896c53e791714b068e88daecf))


## v0.1.0 (2026-07-23)

- Initial Release
