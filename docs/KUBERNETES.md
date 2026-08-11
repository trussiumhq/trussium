# Kubernetes Deployment Guide

Trussium includes a Kustomize base and a production overlay for Kubernetes. The
production deployment runs between two and ten hardened replicas behind a
ClusterIP Service on port 9000 and uses the release image pinned in the overlay.

The independently versioned official
[`trussium` Helm chart](https://github.com/trussiumhq/trussium-helm) packages
the same production contract. Use Helm when values-driven configuration and
Helm-managed install, upgrade, rollback, and uninstall lifecycles are desired.
Use the maintained Kustomize overlay when direct rendered-manifest ownership or
overlay composition is preferred. The chart deploys the runtime only and does
not install the future Trussium Operator.

## Resources

The maintained production overlay renders:

- A dedicated `trussium-system` Namespace.
- A ServiceAccount without API token automounting and with a private-registry
  pull-secret reference.
- A ConfigMap for non-secret runtime settings.
- A Deployment with rolling updates and topology spreading.
- A ClusterIP Service on port 9000.
- A PodDisruptionBudget allowing at most one unavailable replica.
- An `autoscaling/v2` HorizontalPodAutoscaler maintaining two to ten replicas
  against the named runtime container's CPU utilization.

Provider credentials are deliberately excluded. The Deployment optionally
loads a `trussium-provider` Secret when one exists.

## Prerequisites

- A Kubernetes cluster with `policy/v1` PodDisruptionBudget and
  `autoscaling/v2` HorizontalPodAutoscaler support.
- A working Kubernetes Metrics API, commonly provided by Metrics Server.
- `kubectl` with integrated Kustomize support.
- Permission to create Namespace, workload, Service, ConfigMap, Secret,
  PodDisruptionBudget, and HorizontalPodAutoscaler resources.
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
- Prometheus-compatible runtime metrics enabled at `/metrics`.
- OpenTelemetry tracing disabled until a collector endpoint is configured.

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

To export traces, patch the non-secret ConfigMap values in a deployment-owned
overlay. The endpoint must be reachable from the pod and normally targets an
OpenTelemetry Collector Service:

```yaml
data:
  TRUSSIUM_OBSERVABILITY__TRACING_ENABLED: "true"
  TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME: "trussium"
  TRUSSIUM_OBSERVABILITY__TRACING_SAMPLE_RATIO: "0.1"
  TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT: "http://otel-collector.observability.svc:4318/v1/traces"
```

Trussium does not install a collector. See the
[OpenTelemetry Tracing Guide](TRACING.md) for sampling, privacy, lifecycle,
and current distributed-propagation boundaries.

## Deploy with Helm

After creating the namespace, image-pull Secret, and any provider Secret above,
authenticate to GHCR and install chart v0.3.0:

```bash
helm registry login ghcr.io --username YOUR_GITHUB_USERNAME

helm install trussium \
  oci://ghcr.io/trussiumhq/charts/trussium \
  --version 0.3.0 \
  --namespace trussium-system \
  --wait
```

Chart v0.3.0 defaults to runtime v0.26.0. Chart and runtime versions are
independent; the chart's `appVersion` records its default compatible runtime.
The chart enables the same two-to-ten-replica CPU HPA and runtime metrics
contract by default, so a working Kubernetes Metrics API is required. It also
renders the runtime's tracing enablement, service identity, sampling ratio,
OTLP HTTP/protobuf endpoint, and export timeout while leaving tracing disabled
by default. The chart does not install a collector or tracing backend. Use fixed
replicas when the Metrics API is intentionally unavailable:

```bash
helm install trussium \
  oci://ghcr.io/trussiumhq/charts/trussium \
  --version 0.3.0 \
  --namespace trussium-system \
  --set autoscaling.enabled=false \
  --set replicaCount=2 \
  --wait
```

The chart repository documents every value, existing Secret integration,
customization, upgrades, rollbacks, removal, and release compatibility.

The remaining sections describe the maintained Kustomize path. Do not manage
the same runtime release with both Helm and Kustomize.

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
kubectl get all,poddisruptionbudget,horizontalpodautoscaler \
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
curl http://127.0.0.1:9000/metrics
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
- Changing autoscaling bounds, CPU target, resource requests, and topology
  rules to match measured demand and cluster size.
- Referencing an organization-managed registry or provider Secret.
- Enabling OTLP trace export to an organization-managed collector.

## Horizontal autoscaling

The maintained production overlay uses an `autoscaling/v2`
HorizontalPodAutoscaler with these conservative defaults:

- Minimum `2` and maximum `10` replicas.
- Average CPU utilization target of `70%` for the named `trussium` container.
- At most a 100% or four-pod increase per 60 seconds, selecting the larger
  permitted scale-up.
- A 300-second scale-down stabilization window.
- At most a 25% or one-pod decrease per 60 seconds, selecting the smaller
  permitted scale-down.

The CPU target is calculated relative to the container's CPU request, so keep
that request representative of observed steady-state use. Metrics Server (or
another resource Metrics API implementation) supplies this standard metric;
Trussium does not install it.

Inspect current status and events:

```bash
kubectl get horizontalpodautoscaler/trussium \
  --namespace trussium-system
kubectl describe horizontalpodautoscaler/trussium \
  --namespace trussium-system
```

Do not declare `spec.replicas` in a production Deployment patch managed by the
autoscaler. Reapplying a conflicting replica count can cause unnecessary
scaling churn. Patch the HorizontalPodAutoscaler's bounds or omit it in a
deployment-owned overlay when fixed manual scaling is required.

The `/metrics` endpoint additionally exposes
`trussium_http_requests_active`, which remains accurate for active SSE streams.
It is not used by the default HPA. A deployment-owned Prometheus Adapter rule
can publish that gauge to Kubernetes Custom Metrics API without changing the
bounded metric-label contract. See the [Runtime Metrics Guide](METRICS.md).

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
cluster, loads the image, installs a pinned Metrics Server, applies the rendered
production resources, waits for both replicas, verifies that the autoscaler is
active against live CPU metrics, checks security and disruption settings, and
exercises liveness, readiness, runtime metrics, and request correlation through
the Service.

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
