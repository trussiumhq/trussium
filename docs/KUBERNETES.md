# Kubernetes Deployment Guide

Trussium includes a Kustomize base and a production overlay for Kubernetes. The
production deployment runs two hardened replicas behind a ClusterIP Service on
port 9000 and uses the release image pinned in the overlay.

## Resources

The maintained production overlay renders:

- A dedicated `trussium-system` Namespace.
- A ServiceAccount without API token automounting and with a private-registry
  pull-secret reference.
- A ConfigMap for non-secret runtime settings.
- A two-replica Deployment with rolling updates and topology spreading.
- A ClusterIP Service on port 9000.
- A PodDisruptionBudget allowing at most one unavailable replica.

Provider credentials are deliberately excluded. The Deployment optionally
loads a `trussium-provider` Secret when one exists.

## Prerequisites

- A Kubernetes cluster with `policy/v1` PodDisruptionBudget support.
- `kubectl` with integrated Kustomize support.
- Permission to create Namespace, workload, Service, ConfigMap, Secret, and
  PodDisruptionBudget resources.
- Access to `ghcr.io/trussiumhq/trussium`.

The Trussium GHCR package is private. Create a classic GitHub personal access
token with `read:packages`, then create the referenced registry Secret. Do not
place the token in the repository or shell history.

```bash
kubectl apply -f deploy/kubernetes/base/namespace.yaml

kubectl create secret docker-registry ghcr-credentials \
  --namespace trussium-system \
  --docker-server ghcr.io \
  --docker-username YOUR_GITHUB_USERNAME \
  --docker-password YOUR_GITHUB_TOKEN
```

If the package becomes public, remove `imagePullSecrets` from the
ServiceAccount or keep the Secret for authenticated pulls.

## Provider configuration

The ConfigMap contains safe production defaults:

- Production environment selection.
- Port 9000 and all-interface binding.
- A 30-second graceful-shutdown drain deadline.
- Provider-request and stream-idle deadlines.

Create provider configuration through Kubernetes Secret management. For
OpenAI:

```bash
kubectl create secret generic trussium-provider \
  --namespace trussium-system \
  --from-literal=TRUSSIUM_PROVIDER__NAME=openai \
  --from-literal=TRUSSIUM_PROVIDER__API_KEY=YOUR_PROVIDER_CREDENTIAL
```

For Ollama or another reachable compatible endpoint:

```bash
kubectl create secret generic trussium-provider \
  --namespace trussium-system \
  --from-literal=TRUSSIUM_PROVIDER__NAME=ollama \
  --from-literal=TRUSSIUM_PROVIDER__BASE_URL=http://ollama.ollama.svc:11434/v1
```

The checked-in `deploy/kubernetes/secret.example.yaml` documents the expected
keys, but must not be applied until its placeholder is replaced. External
Secrets, Sealed Secrets, or a cloud secret-store CSI driver can create the same
`trussium-provider` Secret without changing the Deployment.

Health endpoints remain available when the optional provider Secret is absent.

## Validate and deploy

With a reachable cluster selected in the current context, render and perform
Kubernetes client-side schema validation before applying:

```bash
scripts/kubernetes-validate.sh
kubectl diff -k deploy/kubernetes/overlays/production
kubectl apply -k deploy/kubernetes/overlays/production
```

Wait for the zero-unavailable rollout:

```bash
kubectl rollout status \
  --namespace trussium-system \
  deployment/trussium \
  --timeout=180s
```

Inspect the deployed resources:

```bash
kubectl get all,poddisruptionbudget \
  --namespace trussium-system \
  --selector app.kubernetes.io/name=trussium
```

Test the internal Service from a local workstation:

```bash
kubectl port-forward \
  --namespace trussium-system \
  service/trussium 9000:9000
```

In another terminal:

```bash
curl http://127.0.0.1:9000/health/live
curl http://127.0.0.1:9000/health/ready
```

## Customize safely

Do not edit the maintained base directly for a deployment-specific change.
Create another overlay that references `deploy/kubernetes/base` or copy the
production overlay into deployment configuration you control.

Common customizations include:

- Updating `images[].newTag` to an immutable released version.
- Patching the ConfigMap with provider name or base URL settings that are not
  secret.
- Adjusting resource requests and limits from measured usage.
- Changing replica count and topology rules to match cluster size.
- Referencing an organization-managed registry or provider Secret.

The maintained production overlay uses two replicas. Manual horizontal scaling
is supported:

```bash
kubectl scale deployment/trussium \
  --namespace trussium-system \
  --replicas=4
```

Reapplying the production overlay restores its declared replica count. Use a
separate overlay when another count is the desired steady state. Horizontal
autoscaling is not included yet.

## Health, security, and shutdown

The startup probe gates liveness and readiness until the runtime starts. The
readiness probe removes unavailable pods from Service endpoints, while the
liveness probe restarts unhealthy processes.

Pods use the image's numeric user and group `10001:10001`, RuntimeDefault
seccomp, a read-only root filesystem, no privilege escalation, and no Linux
capabilities. The Deployment does not mount a service-account token.

Kubernetes allows 36 seconds for termination: the default 30-second active-work
drain, Trussium's one-second cancellation cleanup allowance, and the recommended
five-second operational margin. If
`TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS` changes, update
`terminationGracePeriodSeconds` to remain at least six seconds longer.

## Upgrade and rollback

Semantic release updates the maintained production overlay's image tag at each
release. For deployment-owned overlays, set the immutable target version,
review the diff, and apply it:

```bash
kubectl diff -k deploy/kubernetes/overlays/production
kubectl apply -k deploy/kubernetes/overlays/production
kubectl rollout status --namespace trussium-system deployment/trussium
```

Inspect rollout history and return to the preceding Deployment revision when
needed:

```bash
kubectl rollout history --namespace trussium-system deployment/trussium
kubectl rollout undo --namespace trussium-system deployment/trussium
kubectl rollout status --namespace trussium-system deployment/trussium
```

Reconcile the overlay's pinned tag after an emergency rollback so the declared
configuration matches the running revision.

## Local cluster smoke test

The complete smoke test builds the local image, creates or reuses a Kind
cluster, loads the image, applies the rendered production resources, waits for
both replicas, verifies security and disruption settings, and exercises
liveness, readiness, and request correlation through the Service.

```bash
scripts/kubernetes-smoke-test.sh
```

Set `TRUSSIUM_KIND_CLUSTER` to reuse an existing Kind cluster. A cluster created
by the script is deleted automatically; a reused cluster is preserved.

## Remove

Delete the managed Namespace and all namespaced Trussium resources:

```bash
kubectl delete namespace trussium-system
```

The operation is destructive for every resource placed in that Namespace.
