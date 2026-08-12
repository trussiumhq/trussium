"""Static and rendered contracts for production Kubernetes deployment."""

import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_KUBERNETES_ROOT = _REPOSITORY_ROOT / "deploy" / "kubernetes"
_PRODUCTION_OVERLAY = _KUBERNETES_ROOT / "overlays" / "production"
_PROJECT_CONFIGURATION = tomllib.loads(
    (_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
)
_PROJECT_VERSION = cast(str, _PROJECT_CONFIGURATION["project"]["version"])


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def test_base_contains_namespaced_runtime_resources() -> None:
    """The base should define the reusable runtime and network contract."""
    kustomization = _load_yaml(_KUBERNETES_ROOT / "base" / "kustomization.yaml")

    assert kustomization["namespace"] == "trussium-system"
    assert set(kustomization["resources"]) == {
        "namespace.yaml",
        "service-account.yaml",
        "config-map.yaml",
        "deployment.yaml",
        "service.yaml",
    }

    namespace = _load_yaml(_KUBERNETES_ROOT / "base" / "namespace.yaml")
    service_account = _load_yaml(_KUBERNETES_ROOT / "base" / "service-account.yaml")
    service = _load_yaml(_KUBERNETES_ROOT / "base" / "service.yaml")

    assert namespace["metadata"]["name"] == "trussium-system"
    assert service_account["automountServiceAccountToken"] is False
    assert service_account["imagePullSecrets"] == [{"name": "ghcr-credentials"}]
    assert service["spec"]["type"] == "ClusterIP"
    assert service["spec"]["ports"] == [
        {"name": "http", "port": 9000, "targetPort": "http", "protocol": "TCP"}
    ]


def test_deployment_matches_container_security_health_and_shutdown_contract() -> None:
    """Pod settings should preserve the hardened image and lifecycle guarantees."""
    deployment = _load_yaml(_KUBERNETES_ROOT / "base" / "deployment.yaml")
    pod_spec = deployment["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]

    assert pod_spec["serviceAccountName"] == "trussium"
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["enableServiceLinks"] is False
    assert pod_spec["terminationGracePeriodSeconds"] == 36
    assert pod_spec["securityContext"] == {
        "runAsNonRoot": True,
        "runAsUser": 10001,
        "runAsGroup": 10001,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    assert container["ports"] == [{"name": "http", "containerPort": 9000, "protocol": "TCP"}]
    assert container["startupProbe"]["httpGet"] == {
        "path": "/health/live",
        "port": "http",
    }
    assert container["livenessProbe"]["httpGet"] == {
        "path": "/health/live",
        "port": "http",
    }
    assert container["readinessProbe"]["httpGet"] == {
        "path": "/health/ready",
        "port": "http",
    }
    assert container["envFrom"] == [
        {"configMapRef": {"name": "trussium"}},
        {"secretRef": {"name": "trussium-provider", "optional": True}},
    ]


def test_config_map_and_secret_example_separate_safe_and_sensitive_settings() -> None:
    """Non-secret defaults should be tracked while credentials remain placeholders."""
    config_map = _load_yaml(_KUBERNETES_ROOT / "base" / "config-map.yaml")
    example_secret = _load_yaml(_KUBERNETES_ROOT / "secret.example.yaml")

    assert config_map["data"] == {
        "TRUSSIUM_ENVIRONMENT": "production",
        "TRUSSIUM_OBSERVABILITY__METRICS_ENABLED": "true",
        "TRUSSIUM_OBSERVABILITY__TRACING_ENABLED": "false",
        "TRUSSIUM_RUNTIME__HOST": "0.0.0.0",
        "TRUSSIUM_RUNTIME__PORT": "9000",
        "TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS": "30",
        "TRUSSIUM_READINESS__DEPENDENCY_CHECKS_ENABLED": "false",
        "TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS": "1",
        "TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS": "10",
        "TRUSSIUM_TIMEOUTS__PROVIDER_REQUEST_SECONDS": "60",
        "TRUSSIUM_TIMEOUTS__STREAM_IDLE_SECONDS": "30",
    }
    assert "API_KEY" not in " ".join(config_map["data"])
    assert example_secret["metadata"]["name"] == "trussium-provider"
    assert example_secret["stringData"]["TRUSSIUM_PROVIDER__API_KEY"].startswith("replace-with-")


def test_production_overlay_defines_availability_and_release_image_contract() -> None:
    """Production should be replicated, disruption-aware, and release pinned."""
    kustomization = _load_yaml(_PRODUCTION_OVERLAY / "kustomization.yaml")
    patch = _load_yaml(_PRODUCTION_OVERLAY / "deployment-patch.yaml")
    disruption_budget = _load_yaml(_PRODUCTION_OVERLAY / "pod-disruption-budget.yaml")
    autoscaler = _load_yaml(_PRODUCTION_OVERLAY / "horizontal-pod-autoscaler.yaml")

    assert kustomization["resources"] == [
        "../../base",
        "horizontal-pod-autoscaler.yaml",
        "pod-disruption-budget.yaml",
    ]
    assert kustomization["patches"] == [{"path": "deployment-patch.yaml"}]
    assert kustomization["images"] == [
        {
            "name": "ghcr.io/trussiumhq/trussium",
            "newName": "ghcr.io/trussiumhq/trussium",
            "newTag": _PROJECT_VERSION,
        }
    ]
    assert "replicas" not in patch["spec"]
    assert patch["spec"]["strategy"] == {
        "type": "RollingUpdate",
        "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
    }
    assert (
        patch["spec"]["template"]["spec"]["topologySpreadConstraints"][0]["topologyKey"]
        == "kubernetes.io/hostname"
    )
    assert disruption_budget["apiVersion"] == "policy/v1"
    assert disruption_budget["spec"]["maxUnavailable"] == 1
    assert autoscaler["apiVersion"] == "autoscaling/v2"
    assert autoscaler["spec"]["scaleTargetRef"] == {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "name": "trussium",
    }
    assert autoscaler["spec"]["minReplicas"] == 2
    assert autoscaler["spec"]["maxReplicas"] == 10
    assert autoscaler["spec"]["metrics"] == [
        {
            "type": "ContainerResource",
            "containerResource": {
                "name": "cpu",
                "container": "trussium",
                "target": {"type": "Utilization", "averageUtilization": 70},
            },
        }
    ]
    assert autoscaler["spec"]["behavior"]["scaleUp"] == {
        "stabilizationWindowSeconds": 0,
        "selectPolicy": "Max",
        "policies": [
            {"type": "Percent", "value": 100, "periodSeconds": 60},
            {"type": "Pods", "value": 4, "periodSeconds": 60},
        ],
    }
    assert autoscaler["spec"]["behavior"]["scaleDown"] == {
        "stabilizationWindowSeconds": 300,
        "selectPolicy": "Min",
        "policies": [
            {"type": "Percent", "value": 25, "periodSeconds": 60},
            {"type": "Pods", "value": 1, "periodSeconds": 60},
        ],
    }


@pytest.mark.skipif(shutil.which("kubectl") is None, reason="kubectl is not installed")
def test_production_overlay_renders_complete_deployment() -> None:
    """Kustomize should merge the production overlay into the expected resources."""
    result = subprocess.run(
        ["kubectl", "kustomize", str(_PRODUCTION_OVERLAY)],
        check=True,
        capture_output=True,
        text=True,
    )
    documents = [
        cast(dict[str, Any], document)
        for document in yaml.safe_load_all(result.stdout)
        if isinstance(document, dict)
    ]
    by_kind = {document["kind"]: document for document in documents}

    assert set(by_kind) == {
        "Namespace",
        "ServiceAccount",
        "ConfigMap",
        "Service",
        "Deployment",
        "HorizontalPodAutoscaler",
        "PodDisruptionBudget",
    }
    namespaced_documents = [document for document in documents if document["kind"] != "Namespace"]
    assert all(
        document["metadata"]["namespace"] == "trussium-system" for document in namespaced_documents
    )
    deployment = by_kind["Deployment"]
    assert deployment["spec"]["replicas"] == 1
    assert deployment["spec"]["template"]["spec"]["containers"][0]["image"] == (
        f"ghcr.io/trussiumhq/trussium:{_PROJECT_VERSION}"
    )
    autoscaler = by_kind["HorizontalPodAutoscaler"]
    assert autoscaler["spec"]["scaleTargetRef"]["name"] == "trussium"
    assert autoscaler["spec"]["minReplicas"] == 2


def test_release_automation_stamps_the_production_image_tag() -> None:
    """Semantic releases should keep the deployment image aligned with the release."""
    assert _PROJECT_CONFIGURATION["tool"]["semantic_release"]["version_variables"] == [
        "deploy/kubernetes/overlays/production/kustomization.yaml:newTag"
    ]


def test_kubernetes_validation_is_executable_and_runs_in_ci() -> None:
    """Both structural and real-cluster deployment checks should be automated."""
    validate_path = _REPOSITORY_ROOT / "scripts" / "kubernetes-validate.sh"
    smoke_path = _REPOSITORY_ROOT / "scripts" / "kubernetes-smoke-test.sh"
    workflow = (_REPOSITORY_ROOT / ".github" / "workflows" / "kubernetes.yml").read_text()

    assert validate_path.stat().st_mode & 0o100
    assert smoke_path.stat().st_mode & 0o100
    assert "kubectl kustomize" in validate_path.read_text()
    assert 'kubectl apply --dry-run=client -f "$rendered"' in validate_path.read_text()
    assert "kind create cluster" in smoke_path.read_text()
    assert 'metrics_server_version="v0.8.1"' in smoke_path.read_text()
    assert "metrics-server/releases/download/$metrics_server_version/components.yaml" in (
        smoke_path.read_text()
    )
    assert "horizontalpodautoscaler/trussium" in smoke_path.read_text()
    assert "ScalingActive" in smoke_path.read_text()
    assert "rollout status deployment/trussium" in smoke_path.read_text()
    assert "kubernetes-smoke-69" in smoke_path.read_text()
    assert '"event":"runtime.configuration.loaded"' in smoke_path.read_text()
    assert '"event":"provider.configuration.unavailable"' in smoke_path.read_text()
    assert "uses: helm/kind-action@v1" in workflow
    assert "run: scripts/kubernetes-validate.sh" in workflow
    assert "run: scripts/kubernetes-smoke-test.sh" in workflow
