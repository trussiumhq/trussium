"""Static contract tests for production container packaging."""

from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_uses_locked_multi_stage_production_install() -> None:
    """The runtime image should contain only a non-editable production install."""
    dockerfile = (_REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM --platform=${BUILDPLATFORM} ${PYTHON_IMAGE} AS package-builder" in dockerfile
    assert "FROM ${UV_IMAGE} AS uv" in dockerfile
    assert "FROM ${PYTHON_IMAGE} AS builder" in dockerfile
    assert "FROM ${PYTHON_IMAGE} AS runtime" in dockerfile
    assert "UV_NO_DEV=1" in dockerfile
    assert "uv build --wheel --out-dir /dist" in dockerfile
    assert "uv sync --frozen --no-dev --no-install-project --no-editable" in dockerfile
    assert (
        "uv pip install --python /app/.venv/bin/python --no-deps /dist/trussium-*.whl"
    ) in dockerfile
    assert "COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv" in dockerfile

    runtime_stage = dockerfile.split("FROM ${PYTHON_IMAGE} AS runtime", maxsplit=1)[1]
    assert "COPY --from=uv" not in runtime_stage
    assert "COPY src" not in runtime_stage


def test_dockerfile_declares_hardened_runtime_contract() -> None:
    """The image should expose stable identity, health, and process metadata."""
    dockerfile = (_REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "USER 10001:10001" in dockerfile
    assert "EXPOSE 9000" in dockerfile
    assert "HEALTHCHECK --interval=30s" in dockerfile
    assert "--start-period=30s --start-interval=2s" in dockerfile
    assert "http://127.0.0.1:9000/health/live" in dockerfile
    assert "STOPSIGNAL SIGTERM" in dockerfile
    assert 'ENTRYPOINT ["python", "-m", "trussium"]' in dockerfile
    assert "TRUSSIUM_RUNTIME__HOST=0.0.0.0" in dockerfile
    assert "TRUSSIUM_RUNTIME__PORT=9000" in dockerfile
    assert 'org.opencontainers.image.licenses="Apache-2.0"' in dockerfile


def test_dockerignore_uses_a_minimal_allowlist() -> None:
    """Local state, credentials, tests, and VCS data should stay out of builds."""
    entries = set((_REPOSITORY_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines())

    assert entries == {
        "*",
        "!pyproject.toml",
        "!uv.lock",
        "!README.md",
        "!LICENSE",
        "!src/",
        "!src/**",
        "**/__pycache__/",
        "**/*.py[cod]",
    }


def test_smoke_script_validates_runtime_security_and_shutdown() -> None:
    """The executable smoke test should exercise the production container."""
    script_path = _REPOSITORY_ROOT / "scripts/container-smoke-test.sh"
    script = script_path.read_text(encoding="utf-8")

    assert script_path.stat().st_mode & 0o100
    assert "--read-only" in script
    assert "--cap-drop ALL" in script
    assert "no-new-privileges:true" in script
    assert "container-smoke-61" in script
    assert '"http://127.0.0.1:${host_port}/metrics"' in script
    assert '"http://127.0.0.1:${host_port}/health/components"' in script
    assert "component health body" in script
    assert '"http://127.0.0.1:${host_port}/v1/capabilities"' in script
    assert "capability discovery body" in script
    assert '"http://127.0.0.1:${host_port}/v1/capabilities/availability"' in script
    assert "capability availability body" in script
    assert "RuntimeComponentHealthReporter" in script
    assert "CapabilityAvailabilityReporter" in script
    assert "CapabilityAvailabilityStatus" in script
    assert "CHAT_CAPABILITY_NAME" in script
    assert "CHAT_CAPABILITY_METADATA" in script
    assert "CapabilityRegistry" in script
    assert "CapabilityExecutionPipeline" in script
    assert "CapabilityInvocation" in script
    assert "middleware=(middleware,)" in script
    assert "pipeline.middleware == (middleware,)" in script
    assert "pipeline.execute(" in script
    assert "trussium_http_requests_active" in script
    assert "process_start_time_seconds" in script
    assert 'docker exec "$container" id -u' in script
    assert 'docker stop --time 10 "$container"' in script
    assert "graceful shutdown exit code" in script
    assert '"event":"runtime.configuration.loaded"' in script
    assert '"event":"runtime.shutdown.completed"' in script
    assert "uv must not be present" in script
    assert "issubclass(ProviderError, TrussiumError)" in script


def test_container_workflow_validates_and_publishes_release_images() -> None:
    """CI should smoke-test changes and publish hardened release manifests."""
    workflow = (_REPOSITORY_ROOT / ".github/workflows/container.yml").read_text(encoding="utf-8")

    assert "docker build --check ." in workflow
    assert "scripts/container-smoke-test.sh" in workflow
    assert "workflow_dispatch:" in workflow
    assert "if: startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "ghcr.io/${{ github.repository }}" in workflow
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "push: true" in workflow
    assert "provenance: mode=max" in workflow
    assert "sbom: true" in workflow


def test_release_workflow_dispatches_new_tags_for_container_publication() -> None:
    """A semantic release should explicitly start the tagged image workflow."""
    workflow = (_REPOSITORY_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "id: previous-release" in workflow
    assert "id: release" in workflow
    assert "PREVIOUS_RELEASE_TAG: ${{ steps.previous-release.outputs.tag }}" in workflow
    assert "if: steps.release.outputs.tag != ''" in workflow
    assert "actions: write" in workflow
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert 'gh workflow run container.yml --ref "$RELEASE_TAG"' in workflow
