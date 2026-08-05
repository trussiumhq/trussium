#!/bin/sh

set -eu

repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
overlay="$repository_root/deploy/kubernetes/overlays/production"
rendered="$(mktemp)"

cleanup() {
    rm -f "$rendered"
}

trap cleanup EXIT INT TERM

command -v kubectl >/dev/null 2>&1 || {
    echo "kubectl is required for Kubernetes validation" >&2
    exit 1
}

kubectl kustomize "$overlay" >"$rendered"

if grep -Eq 'image: .*:(latest|main)$' "$rendered"; then
    echo "production manifests must use an immutable release image tag" >&2
    exit 1
fi

kubectl apply --dry-run=client -f "$rendered" >/dev/null

echo "Kubernetes manifests rendered and passed client-side validation"
