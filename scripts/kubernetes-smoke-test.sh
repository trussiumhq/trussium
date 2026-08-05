#!/bin/sh

set -eu

repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cluster="${TRUSSIUM_KIND_CLUSTER:-trussium-smoke-$$}"
context="kind-$cluster"
namespace="trussium-system"
image="${TRUSSIUM_KUBERNETES_IMAGE:-trussium:kubernetes-smoke}"
rendered="$(mktemp)"
headers="$(mktemp)"
body="$(mktemp)"
port_forward_log="$(mktemp)"
created_cluster=false
port_forward_pid=""

cleanup() {
    if [ -n "$port_forward_pid" ]; then
        kill "$port_forward_pid" >/dev/null 2>&1 || true
        wait "$port_forward_pid" >/dev/null 2>&1 || true
    fi

    if [ "$created_cluster" = true ]; then
        kind delete cluster --name "$cluster" >/dev/null 2>&1 || true
    fi

    rm -f "$rendered" "$headers" "$body" "$port_forward_log"
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

for command_name in docker kind kubectl curl python3; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "$command_name is required for the Kubernetes smoke test" >&2
        exit 1
    }
done

if ! kind get clusters | grep -Fx "$cluster" >/dev/null 2>&1; then
    kind create cluster --name "$cluster" --wait 90s
    created_cluster=true
fi

docker build --quiet --tag "$image" "$repository_root"
kind load docker-image "$image" --name "$cluster"

"$repository_root/scripts/kubernetes-validate.sh"
kubectl kustomize "$repository_root/deploy/kubernetes/overlays/production" \
    | sed "s|image: ghcr.io/trussiumhq/trussium:[^[:space:]]*|image: $image|" \
    >"$rendered"
kubectl --context "$context" apply -f "$rendered"
kubectl --context "$context" -n "$namespace" rollout status deployment/trussium \
    --timeout=180s

assert_equal "$(kubectl --context "$context" -n "$namespace" get deployment trussium \
    -o jsonpath='{.status.readyReplicas}')" "2" "ready replicas"
assert_equal "$(kubectl --context "$context" -n "$namespace" get deployment trussium \
    -o jsonpath='{.spec.template.spec.securityContext.runAsUser}')" "10001" "runtime UID"
assert_equal "$(kubectl --context "$context" -n "$namespace" get deployment trussium \
    -o jsonpath='{.spec.template.spec.securityContext.runAsGroup}')" "10001" "runtime GID"
assert_equal "$(kubectl --context "$context" -n "$namespace" get deployment trussium \
    -o jsonpath='{.spec.template.spec.containers[0].securityContext.readOnlyRootFilesystem}')" \
    "true" "read-only root filesystem"
assert_equal "$(kubectl --context "$context" -n "$namespace" get deployment trussium \
    -o jsonpath='{.spec.template.spec.terminationGracePeriodSeconds}')" "36" \
    "termination grace period"
assert_equal "$(kubectl --context "$context" -n "$namespace" get poddisruptionbudget trussium \
    -o jsonpath='{.spec.maxUnavailable}')" "1" "maximum unavailable pods"

port="$(python3 -c 'import socket; sock = socket.socket(); sock.bind(("127.0.0.1", 0)); print(sock.getsockname()[1]); sock.close()')"
kubectl --context "$context" -n "$namespace" port-forward service/trussium \
    "$port:9000" >"$port_forward_log" 2>&1 &
port_forward_pid=$!

attempt=0
until curl --fail --silent "http://127.0.0.1:$port/health/live" >/dev/null 2>&1; do
    if ! kill -0 "$port_forward_pid" >/dev/null 2>&1; then
        cat "$port_forward_log" >&2
        echo "Kubernetes port-forward exited before the runtime became reachable" >&2
        exit 1
    fi

    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        kubectl --context "$context" -n "$namespace" get pods >&2
        kubectl --context "$context" -n "$namespace" logs \
            -l app.kubernetes.io/name=trussium --tail=100 >&2
        echo "Kubernetes runtime did not become reachable within 60 seconds" >&2
        exit 1
    fi
    sleep 1
done

assert_equal "$(curl --fail --silent "http://127.0.0.1:$port/health/live")" \
    '{"status":"ok"}' "liveness response"

curl --fail --silent --show-error \
    "http://127.0.0.1:$port/health/ready" \
    --header "X-Request-ID: kubernetes-smoke-69" \
    --dump-header "$headers" \
    --output "$body"

assert_equal "$(cat "$body")" '{"status":"ok"}' "readiness response"
request_id="$(awk 'tolower($1) == "x-request-id:" {gsub("\r", "", $2); print $2}' "$headers")"
assert_equal "$request_id" "kubernetes-smoke-69" "request correlation header"

echo "Kubernetes smoke test passed for $image on Kind cluster $cluster"
