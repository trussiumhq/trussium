#!/bin/sh

set -eu

image="${TRUSSIUM_CONTAINER_IMAGE:-trussium:smoke}"
container="trussium-smoke-$$"
repository="https://github.com/trussiumhq/trussium"
revision="$(git rev-parse HEAD)"
build_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
response_headers="$(mktemp)"
response_body="$(mktemp)"

cleanup() {
    docker rm --force "$container" >/dev/null 2>&1 || true
    rm -f "$response_headers" "$response_body"
}

trap cleanup EXIT INT TERM

assert_equal() {
    actual="$1"
    expected="$2"
    description="$3"

    if [ "$actual" != "$expected" ]; then
        echo "$description: expected '$expected', got '$actual'" >&2
        exit 1
    fi
}

docker build \
    --quiet \
    --build-arg BUILD_DATE="$build_date" \
    --build-arg SOURCE_URL="$repository" \
    --build-arg VCS_REF="$revision" \
    --build-arg VERSION="smoke" \
    --tag "$image" \
    .

assert_equal "$(docker image inspect --format '{{.Config.User}}' "$image")" \
    "10001:10001" "runtime user"
assert_equal "$(docker image inspect --format '{{json .Config.Entrypoint}}' "$image")" \
    '["python","-m","trussium"]' "entry point"
assert_equal "$(docker image inspect --format '{{.Config.StopSignal}}' "$image")" \
    "SIGTERM" "stop signal"
assert_equal "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.version"}}' "$image")" \
    "smoke" "OCI version label"
assert_equal "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")" \
    "$revision" "OCI revision label"
assert_equal "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.source"}}' "$image")" \
    "$repository" "OCI source label"
assert_equal "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.licenses"}}' "$image")" \
    "Apache-2.0" "OCI license label"
assert_equal "$(docker image inspect --format '{{json .Config.ExposedPorts}}' "$image")" \
    '{"9000/tcp":{}}' "exposed port"

healthcheck="$(docker image inspect --format '{{json .Config.Healthcheck.Test}}' "$image")"

if [ "$healthcheck" = "null" ] || [ -z "$healthcheck" ]; then
    echo "image health check is missing" >&2
    exit 1
fi

docker run --rm --entrypoint python "$image" -c \
    "import importlib.util; assert importlib.util.find_spec('pytest') is None"
docker run --rm --entrypoint python "$image" -c \
    "from trussium import ProviderError, TrussiumError; assert issubclass(ProviderError, TrussiumError); assert ProviderError('safe').code == 'provider_error'"
docker run --rm --entrypoint python "$image" -c \
    "from trussium.runtime import RuntimeComponentHealthReporter, RuntimeComponentStatus; assert RuntimeComponentHealthReporter is not None; assert RuntimeComponentStatus.OK == 'ok'"
docker run --rm --entrypoint python "$image" -c \
    "from trussium.capabilities import CapabilityAvailabilityReporter, CapabilityAvailabilityStatus; assert CapabilityAvailabilityReporter is not None; assert CapabilityAvailabilityStatus.AVAILABLE == 'available'"
docker run --rm --entrypoint python "$image" -c \
    "import asyncio; from trussium.capabilities import CHAT_CAPABILITY_METADATA, CHAT_CAPABILITY_NAME, CapabilityExecutionPipeline, CapabilityInvocation, CapabilityRegistry; capability = object(); registry = CapabilityRegistry(); assert registry.register(CHAT_CAPABILITY_NAME, capability, metadata=CHAT_CAPABILITY_METADATA) is capability; assert registry.seal()[0].metadata is CHAT_CAPABILITY_METADATA; invocations = []; middleware = type('SmokeMiddleware', (), {'execute': lambda self, invocation, call_next: (invocations.append(invocation), call_next())[1], 'stream': lambda self, invocation, call_next: call_next()})(); pipeline = CapabilityExecutionPipeline(registry, middleware=(middleware,)); assert asyncio.run(pipeline.execute(CHAT_CAPABILITY_NAME, lambda resolved: asyncio.sleep(0, result=resolved))) is capability; assert pipeline.middleware == (middleware,); assert len(invocations) == 1; assert isinstance(invocations[0], CapabilityInvocation); assert invocations[0].capability is capability"

if docker run --rm --entrypoint sh "$image" -c 'command -v uv >/dev/null'; then
    echo "uv must not be present in the runtime image" >&2
    exit 1
fi

docker run \
    --detach \
    --name "$container" \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --publish 127.0.0.1::9000 \
    "$image" >/dev/null

port_mapping="$(docker port "$container" 9000/tcp)"
host_port="${port_mapping##*:}"
attempt=0

while [ "$attempt" -lt 60 ]; do
    state="$(docker inspect --format '{{.State.Status}}' "$container")"
    health="$(docker inspect --format '{{.State.Health.Status}}' "$container")"

    if [ "$state" != "running" ]; then
        docker logs "$container" >&2
        echo "container exited before becoming healthy" >&2
        exit 1
    fi

    if [ "$health" = "healthy" ]; then
        break
    fi

    attempt=$((attempt + 1))
    sleep 1
done

if [ "$health" != "healthy" ]; then
    docker inspect "$container" >&2
    docker logs "$container" >&2
    echo "container did not become healthy within 60 seconds" >&2
    exit 1
fi

curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/health/ready" \
    --header "X-Request-ID: container-smoke-61" \
    --dump-header "$response_headers" \
    --output "$response_body"

assert_equal "$(cat "$response_body")" '{"status":"ok"}' "readiness body"

request_id="$(awk 'tolower($1) == "x-request-id:" {gsub("\r", "", $2); print $2}' "$response_headers")"
assert_equal "$request_id" "container-smoke-61" "request correlation header"

curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/health/components" \
    --output "$response_body"

assert_equal "$(cat "$response_body")" \
    '{"status":"ok","components":[]}' "component health body"

curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/v1/capabilities" \
    --output "$response_body"

assert_equal "$(cat "$response_body")" \
    '{"capabilities":[]}' "capability discovery body"

curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/v1/capabilities/availability" \
    --output "$response_body"

assert_equal "$(cat "$response_body")" \
    '{"status":"available","capabilities":[]}' "capability availability body"

curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/metrics" \
    --output "$response_body"

grep -q '^trussium_http_requests_active 0\.0$' "$response_body"
grep -q '^process_start_time_seconds ' "$response_body"

assert_equal "$(docker exec "$container" id -u)" "10001" "runtime UID"
assert_equal "$(docker exec "$container" id -g)" "10001" "runtime GID"

docker logs "$container" 2>&1 | grep -q '"event":"runtime.configuration.loaded"'
docker logs "$container" 2>&1 | grep -q '"event":"provider.configuration.unavailable"'
docker logs "$container" 2>&1 | grep -q '"event":"runtime.started"'

docker stop --time 10 "$container" >/dev/null
assert_equal "$(docker inspect --format '{{.State.ExitCode}}' "$container")" "0" \
    "graceful shutdown exit code"
docker logs "$container" 2>&1 | grep -q '"event":"runtime.shutdown.completed"'
docker logs "$container" 2>&1 | grep -q '"outcome":"completed"'

echo "Container smoke test passed for $image"
