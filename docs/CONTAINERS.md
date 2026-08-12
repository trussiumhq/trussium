# Container Guide

Trussium publishes a production-oriented OCI image for Linux AMD64 and ARM64.
The image runs the same `python -m trussium` entry point used in local
development and listens on port 9000.

## Image contract

The production image:

- Uses Python 3.12 on Debian slim.
- Installs the locked runtime dependencies and Trussium package with uv in a
  separate build stage.
- Does not contain uv, Pytest, Ruff, MyPy, the repository source tree, or other
  development dependencies in the final stage.
- Runs as the dedicated numeric user and group `10001:10001`.
- Declares port 9000, a liveness health check, and `SIGTERM` shutdown behavior.
- Supports a read-only root filesystem, dropped Linux capabilities, and
  `no-new-privileges`.
- Carries standard OCI source, revision, version, creation-time, and license
  metadata.

## Pulling a release

Semantic-version releases are published to GitHub Container Registry:

```bash
docker pull ghcr.io/trussiumhq/trussium:<version>
```

Published tags include:

- The immutable full version, such as `0.21.0`.
- Moving major/minor compatibility tags, such as `0.21` and `0`.
- `latest`, which follows the newest semantic release.

Release manifests support `linux/amd64` and `linux/arm64` and include build
provenance and an SBOM.

## Building locally

Run Docker's static build checks:

```bash
docker build --check .
```

Build a local image:

```bash
docker build --tag trussium:local .
```

Build metadata can be supplied explicitly:

```bash
docker build \
  --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --build-arg SOURCE_URL="https://github.com/trussiumhq/trussium" \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  --build-arg VERSION="local" \
  --tag trussium:local \
  .
```

The build context uses an allowlist. Local virtual environments, Git state,
tests, documentation, credentials, caches, and editor files are not sent to
the builder.

## Smoke validation

Run the complete image contract test:

```bash
scripts/container-smoke-test.sh
```

The script builds the image, verifies its metadata and runtime contents, starts
it on a dynamically allocated host port with hardened security options, waits
for Docker health, checks liveness, readiness, process and request metrics, and
request correlation, verifies the runtime UID/GID, and confirms clean
`SIGTERM` shutdown. It always removes the temporary container.

Set `TRUSSIUM_CONTAINER_IMAGE` to choose the local test tag:

```bash
TRUSSIUM_CONTAINER_IMAGE="trussium:validation" \
  scripts/container-smoke-test.sh
```

## Running without a provider

Health endpoints remain available when no provider is configured:

```bash
docker run --rm \
  --name trussium \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --publish 9000:9000 \
  ghcr.io/trussiumhq/trussium:<version>
```

Check container and application health:

```bash
docker inspect --format '{{.State.Health.Status}}' trussium
curl http://127.0.0.1:9000/health/ready
curl http://127.0.0.1:9000/metrics
```

## Running with OpenAI

Pass runtime configuration at container start. Prefer an environment file or
the secret facility provided by the deployment platform instead of placing
credentials directly in a shell command.

Example `.env.openai`:

```text
TRUSSIUM_ENVIRONMENT=production
TRUSSIUM_PROVIDER__NAME=openai
TRUSSIUM_PROVIDER__API_KEY=replace-with-a-secret
```

```bash
docker run --rm \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --env-file .env.openai \
  --publish 9000:9000 \
  ghcr.io/trussiumhq/trussium:<version>
```

Legacy `OPENAI_API_KEY` and `OPENAI_BASE_URL` variables remain supported.

## OpenTelemetry tracing

Tracing is disabled by default. Enable OTLP HTTP/protobuf export through the
container environment only after selecting a collector reachable from the
container network:

```text
TRUSSIUM_OBSERVABILITY__TRACING_ENABLED=true
TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME=trussium
TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO=0.1
TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces
```

The loopback endpoint default refers to the Trussium container itself. See the
[OpenTelemetry Tracing Guide](TRACING.md) for the span hierarchy, structured
log correlation, outbound provider propagation, privacy contract, and
clean-shutdown export behavior.

## Running with Ollama

The container must use a network address that reaches the Ollama server. Inside
a container, `127.0.0.1` refers to the Trussium container itself.

On Docker Desktop:

```bash
docker run --rm \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --env TRUSSIUM_PROVIDER__NAME=ollama \
  --env TRUSSIUM_PROVIDER__BASE_URL=http://host.docker.internal:11434/v1 \
  --publish 9000:9000 \
  ghcr.io/trussiumhq/trussium:<version>
```

On Linux, add the host-gateway mapping when Ollama runs on the Docker host:

```bash
docker run --rm \
  --add-host host.docker.internal:host-gateway \
  --env TRUSSIUM_PROVIDER__NAME=ollama \
  --env TRUSSIUM_PROVIDER__BASE_URL=http://host.docker.internal:11434/v1 \
  --publish 9000:9000 \
  ghcr.io/trussiumhq/trussium:<version>
```

## Health and shutdown

Docker evaluates `GET /health/live` inside the container. The health state
starts as `starting`, becomes `healthy` after a successful probe, and becomes
`unhealthy` after three consecutive failures.

The image uses an exec-form entry point and declares `SIGTERM`. `docker stop`
therefore signals the Python process directly, allowing Uvicorn to complete
application shutdown before the bounded Docker stop timeout expires.

Active requests and streams drain for 30 seconds by default. Set
`TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS` to a positive whole number to
change that deadline. The Docker or orchestrator stop timeout must exceed the
configured drain deadline, Trussium's one-second cancellation-cleanup bound,
and normal exit overhead; a five-second deployment margin is recommended.

See the [Graceful Shutdown Guide](SHUTDOWN.md) for the full signal, draining,
cancellation, structured-log, and deployment-timing contract.

## Publication workflow

Pull requests and pushes to `main` run Docker build checks and the complete
smoke test. When semantic release creates a new tag, the release workflow
explicitly dispatches the container workflow at that tag. The tagged workflow
then builds and publishes the multi-platform image to
`ghcr.io/trussiumhq/trussium` using the GitHub-provided token with package-write
permission. Pull requests never publish images.

## Kubernetes deployment

The repository includes a release-pinned production Kustomize overlay with
health probes, hardened pod security, ConfigMap and optional Secret integration,
rolling updates, disruption protection, and real Kind-cluster validation. See
the [Kubernetes Deployment Guide](KUBERNETES.md).

## Current limitations

The runtime propagates W3C Trace Context to supported provider requests but
does not install a collector, instrument the downstream service, or include
provider-specific model runtimes. The official Helm chart is released
independently from
[`trussiumhq/trussium-helm`](https://github.com/trussiumhq/trussium-helm).
No model weights or provider credentials are bundled in the image.
