#!/bin/sh

set -eu

image="prom/prometheus:v3.6.0@sha256:76947e7ef22f8a698fc638f706685909be425dbe09bd7a2cd7aca849f79b5f64"
repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
rules="deploy/observability/prometheus/rules/trussium-runtime-alerts.yaml"
tests="tests/fixtures/prometheus/trussium-runtime-alerts.test.yaml"

run_promtool() {
    docker run \
        --rm \
        --read-only \
        --tmpfs /tmp:rw,noexec,nosuid,size=32m \
        --network none \
        --cap-drop ALL \
        --security-opt no-new-privileges:true \
        --user 65534:65534 \
        --workdir /workspace \
        --mount "type=bind,source=${repository_root},target=/workspace,readonly" \
        --entrypoint /bin/promtool \
        "$image" \
        "$@"
}

run_promtool check rules "$rules"
run_promtool test rules "$tests"

echo "Prometheus alert rules passed syntax and semantic validation with ${image}"
