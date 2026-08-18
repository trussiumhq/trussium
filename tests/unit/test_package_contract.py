"""Static contracts for Python distribution validation and publication."""

import tomllib
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_package_smoke_script_validates_artifacts_and_installed_runtimes() -> None:
    script_path = _REPOSITORY_ROOT / "scripts/package-smoke-test.sh"
    script = script_path.read_text(encoding="utf-8")

    assert script_path.stat().st_mode & 0o100
    assert "uv build --out-dir" in script
    assert "py3-none-any.whl" in script
    assert "unexpected build output" in script
    assert "source distribution contains unrelated repository files" in script
    assert "uv venv --python" in script
    assert "uv pip install --python" in script
    assert "uv pip check --python" in script
    assert 'metadata.version("trussium") == expected_version' in script
    assert 'resources.files("trussium").joinpath("py.typed").is_file()' in script
    assert '"trussium/errors.py"' in script
    assert '"trussium/runtime/registry.py"' in script
    assert '"trussium/runtime/health.py"' in script
    assert "RuntimeComponentHealthReporter" in script
    assert "RuntimeComponentStatus" in script
    assert "RuntimeServiceRegistry" in script
    assert "RuntimeServiceRegistrySealedError" in script
    assert "registry.seal() == ()" in script
    assert "issubclass(ProviderError, TrussiumError)" in script
    assert '"trussium/observability/tracing.py"' in script
    assert '"opentelemetry-exporter-otlp-proto-http"' in script
    assert '"$python" -m trussium' in script
    assert 'for path in ("/health/live", "/health/ready")' in script
    assert 'f"http://127.0.0.1:{port}/health/components"' in script
    assert '{"status": "ok", "components": []}' in script
    assert 'f"http://127.0.0.1:{port}/metrics"' in script
    assert 'assert "trussium_http_requests_active 0.0" in metrics' in script
    assert 'request_id="package-smoke-65-$label"' in script
    assert 'kill -TERM "$runtime_pid"' in script
    assert "runtime did not stop within 10 seconds" in script
    assert 'grep -q "Application shutdown complete"' in script
    assert '"event":"runtime.configuration.loaded"' in script
    assert '"event":"runtime.shutdown.completed"' in script


def test_package_declares_complete_opentelemetry_runtime_dependencies() -> None:
    configuration = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text())
    dependencies = configuration["project"]["dependencies"]

    assert "opentelemetry-api>=1.44.0" in dependencies
    assert "opentelemetry-sdk>=1.44.0" in dependencies
    assert "opentelemetry-exporter-otlp-proto-http>=1.44.0" in dependencies


def test_ci_has_dedicated_package_build_and_installation_job() -> None:
    workflow = (_REPOSITORY_ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")

    assert "name: Package Build and Installation" in workflow
    assert "timeout-minutes: 10" in workflow
    assert "run: scripts/package-smoke-test.sh" in workflow


def test_release_configuration_uploads_only_python_distribution_artifacts() -> None:
    configuration = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    semantic_release = configuration["tool"]["semantic_release"]
    publish = semantic_release["publish"]

    assert "upload_to_release" not in semantic_release
    assert "upload_to_repository" not in semantic_release
    assert publish == {
        "dist_glob_patterns": ["dist/*.whl", "dist/*.tar.gz"],
        "upload_to_vcs_release": True,
    }


def test_release_workflow_validates_and_publishes_packages_before_containers() -> None:
    workflow = (_REPOSITORY_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    validation = 'scripts/package-smoke-test.sh "$GITHUB_WORKSPACE/dist"'
    publication = 'uv run semantic-release publish --tag "$RELEASE_TAG"'
    container_dispatch = 'gh workflow run container.yml --ref "$RELEASE_TAG"'

    assert "if: steps.release.outputs.tag != ''" in workflow
    assert validation in workflow
    assert publication in workflow
    assert workflow.index(validation) < workflow.index(publication)
    assert workflow.index(publication) < workflow.index(container_dispatch)
