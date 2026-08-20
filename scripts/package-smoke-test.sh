#!/bin/sh

set -eu

repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
temporary_root="${TMPDIR:-/tmp}"
temporary_root="${temporary_root%/}"
work_directory="$(mktemp -d "$temporary_root/trussium-package-smoke.XXXXXX")"
runtime_pid=""

if [ "$#" -gt 1 ]; then
    echo "usage: $0 [absolute-dist-directory]" >&2
    exit 2
fi

if [ "$#" -eq 1 ]; then
    case "$1" in
        /*) distribution_directory="$1" ;;
        *)
            echo "distribution directory must be an absolute path" >&2
            exit 2
            ;;
    esac
else
    distribution_directory="$work_directory/dist"
fi

cleanup() {
    if [ -n "$runtime_pid" ] && kill -0 "$runtime_pid" >/dev/null 2>&1; then
        kill -TERM "$runtime_pid" >/dev/null 2>&1 || true
        wait "$runtime_pid" >/dev/null 2>&1 || true
    fi

    case "$work_directory" in
        "$temporary_root"/trussium-package-smoke.*)
            rm -rf -- "$work_directory"
            ;;
        *)
            echo "refusing to remove unexpected temporary path: $work_directory" >&2
            ;;
    esac
}

trap cleanup EXIT INT TERM HUP

fail() {
    echo "$1" >&2
    exit 1
}

assert_equal() {
    actual="$1"
    expected="$2"
    description="$3"

    if [ "$actual" != "$expected" ]; then
        fail "$description: expected '$expected', got '$actual'"
    fi
}

host_python="$(uv python find 3.12)"
cd "$repository_root"
expected_version="$($host_python -c \
    "import pathlib, tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])")"

wheel="$distribution_directory/trussium-${expected_version}-py3-none-any.whl"
source_distribution="$distribution_directory/trussium-${expected_version}.tar.gz"

mkdir -p "$distribution_directory"
uv build --out-dir "$distribution_directory"

artifact_count="$(find "$distribution_directory" -maxdepth 1 -type f \
    \( -name '*.whl' -o -name '*.tar.gz' \) | wc -l | tr -d ' ')"
assert_equal "$artifact_count" "2" "distribution artifact count"

unexpected_output="$(find "$distribution_directory" -maxdepth 1 -type f \
    ! -name '*.whl' ! -name '*.tar.gz' ! -name '.gitignore' -print)"
[ -z "$unexpected_output" ] || fail "unexpected build output: $unexpected_output"

[ -f "$wheel" ] || fail "expected wheel is missing: $wheel"
[ -f "$source_distribution" ] || fail \
    "expected source distribution is missing: $source_distribution"

"$host_python" - "$wheel" "$source_distribution" "$expected_version" <<'PY'
from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import PurePosixPath


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def dependency_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    require(match is not None, f"invalid Requires-Dist value: {requirement}")
    return match.group(0).lower().replace("_", "-")


wheel_path, source_path, version = sys.argv[1:]
distribution_info = f"trussium-{version}.dist-info"
required_modules = {
    "trussium/__init__.py",
    "trussium/__main__.py",
    "trussium/api/capabilities.py",
    "trussium/api/chat.py",
    "trussium/api/reranking.py",
    "trussium/api/videos.py",
    "trussium/api/transcription.py",
    "trussium/app/factory.py",
    "trussium/capabilities/execution.py",
    "trussium/capabilities/health.py",
    "trussium/capabilities/metadata.py",
    "trussium/capabilities/middleware.py",
    "trussium/capabilities/registry.py",
    "trussium/capabilities/reranking/models.py",
    "trussium/capabilities/videos/models.py",
    "trussium/capabilities/transcription/models.py",
    "trussium/config/settings.py",
    "trussium/errors.py",
    "trussium/middleware/request_tracing.py",
    "trussium/observability/tracing.py",
    "trussium/observability/operations.py",
    "trussium/providers/ollama/chat.py",
    "trussium/providers/openai/chat.py",
    "trussium/providers/openai/transcription.py",
    "trussium/providers/tei/reranking.py",
    "trussium/providers/openai/videos.py",
    "trussium/runtime/context.py",
    "trussium/runtime/health.py",
    "trussium/runtime/registry.py",
    "trussium/py.typed",
}
expected_dependencies = {
    "fastapi",
    "httpx",
    "openai",
    "opentelemetry-api",
    "opentelemetry-exporter-otlp-proto-http",
    "opentelemetry-sdk",
    "prometheus-client",
    "pydantic",
    "pydantic-settings",
    "python-multipart",
    "uvicorn",
}

with zipfile.ZipFile(wheel_path) as archive:
    names = set(archive.namelist())
    require(required_modules <= names, "wheel is missing required package files")
    require(
        all(
            name.startswith("trussium/") or name.startswith(f"{distribution_info}/")
            for name in names
        ),
        "wheel contains files outside the package and distribution metadata",
    )
    require(
        not any(
            "tests" in PurePosixPath(name).parts
            or "__pycache__" in PurePosixPath(name).parts
            or name.endswith((".pyc", ".pyo"))
            for name in names
        ),
        "wheel contains test or cache files",
    )

    metadata_name = f"{distribution_info}/METADATA"
    wheel_metadata_name = f"{distribution_info}/WHEEL"
    license_name = f"{distribution_info}/licenses/LICENSE"
    require({metadata_name, wheel_metadata_name, license_name} <= names, "wheel metadata is incomplete")

    metadata = BytesParser(policy=policy.default).parsebytes(archive.read(metadata_name))
    require(metadata["Name"] == "trussium", "wheel project name is incorrect")
    require(metadata["Version"] == version, "wheel version is incorrect")
    require(metadata["Requires-Python"] == ">=3.12", "wheel Python requirement is incorrect")
    dependencies = {
        dependency_name(value) for value in metadata.get_all("Requires-Dist", failobj=[])
    }
    require(dependencies == expected_dependencies, "wheel runtime dependencies are incorrect")
    require("Apache License" in str(metadata["License"]), "wheel license metadata is incorrect")
    require("# Trussium" in str(metadata.get_payload()), "wheel README metadata is missing")

    wheel_metadata = archive.read(wheel_metadata_name).decode("utf-8")
    require("Tag: py3-none-any" in wheel_metadata, "wheel is not architecture-independent")
    license_text = archive.read(license_name).decode("utf-8")
    require("Apache License" in license_text, "wheel license file is incorrect")

source_root = f"trussium-{version}"
allowed_root_files = {
    f"{source_root}/.gitignore",
    f"{source_root}/LICENSE",
    f"{source_root}/PKG-INFO",
    f"{source_root}/README.md",
    f"{source_root}/pyproject.toml",
}
allowed_directories = {
    source_root,
    f"{source_root}/src",
    f"{source_root}/src/trussium",
}

with tarfile.open(source_path, mode="r:gz") as archive:
    members = archive.getmembers()
    names = {member.name for member in members}
    required_source_files = {
        f"{source_root}/src/{name}" for name in required_modules
    } | allowed_root_files
    require(required_source_files <= names, "source distribution is missing required files")
    require(
        all(member.isfile() or member.isdir() for member in members),
        "source distribution contains links or special files",
    )
    require(
        all(
            name in allowed_root_files
            or name in allowed_directories
            or name.startswith(f"{source_root}/src/trussium/")
            for name in names
        ),
        "source distribution contains unrelated repository files",
    )
    require(
        not any(
            part in {".git", ".github", "tests", "__pycache__", ".venv", "dist", "build"}
            for name in names
            for part in PurePosixPath(name).parts
        ),
        "source distribution contains development or VCS files",
    )
PY

validate_imports() {
    environment="$1"
    artifact="$2"
    label="$3"
    python="$environment/bin/python"

    uv venv --python "$host_python" "$environment"
    uv pip install --python "$python" "$artifact"
    uv pip check --python "$python"

    (
        cd "$work_directory"
        "$python" - "$expected_version" "$repository_root" <<'PY'
from importlib import metadata, resources
from pathlib import Path
import asyncio
import sys

import trussium
from trussium.app import create_application
from trussium.capabilities import (
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    CapabilityAvailabilityReporter,
    CapabilityAvailabilityStatus,
    CapabilityHealthReporter,
    CapabilityHealthStatus,
    CapabilityExecuteNext,
    CapabilityExecutionPipeline,
    CapabilityInvocation,
    CapabilityMetadata,
    CapabilityRegistry,
    CapabilityRegistrySealedError,
    CapabilityStreamNext,
)
from trussium.config.settings import Settings
from trussium.errors import ProviderError, TrussiumError
from trussium.runtime import (
    ExecutionContext,
    RuntimeComponentHealthReporter,
    RuntimeComponentStatus,
    RuntimeServiceRegistry,
    RuntimeServiceRegistrySealedError,
)


expected_version, repository_root = sys.argv[1:]
package_path = Path(trussium.__file__).resolve()
environment_path = Path(sys.prefix).resolve()
repository_path = Path(repository_root).resolve()

assert metadata.version("trussium") == expected_version
assert trussium.__version__ == expected_version
assert environment_path in package_path.parents
assert repository_path not in package_path.parents
assert resources.files("trussium").joinpath("py.typed").is_file()
assert callable(create_application)
assert Settings is not None
assert ExecutionContext is not None
capability = object()
capability_registry = CapabilityRegistry()
assert capability_registry.register(
    CHAT_CAPABILITY_NAME,
    capability,
    metadata=CHAT_CAPABILITY_METADATA,
) is capability
assert capability_registry.names == (CHAT_CAPABILITY_NAME,)
assert capability_registry.metadata == (CHAT_CAPABILITY_METADATA,)
assert capability_registry.require_metadata(CHAT_CAPABILITY_NAME) is CHAT_CAPABILITY_METADATA
assert CapabilityMetadata is not None
assert capability_registry.require(CHAT_CAPABILITY_NAME) is capability
assert capability_registry.seal()[0].capability is capability
assert capability_registry.sealed is True
availability_report = asyncio.run(
    CapabilityAvailabilityReporter(capability_registry).report()
)
assert availability_report.status is CapabilityAvailabilityStatus.AVAILABLE
assert availability_report.capabilities[0].name == CHAT_CAPABILITY_NAME
health_report = asyncio.run(CapabilityHealthReporter(capability_registry).report())
assert health_report.status is CapabilityHealthStatus.UNKNOWN
assert health_report.capabilities[0].name == CHAT_CAPABILITY_NAME


class SmokeMiddleware:
    def __init__(self):
        self.invocations = []

    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        self.invocations.append(invocation)
        return await call_next()

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ):
        self.invocations.append(invocation)
        return call_next()


middleware = SmokeMiddleware()
pipeline = CapabilityExecutionPipeline(
    capability_registry,
    middleware=(middleware,),
)
assert asyncio.run(
    pipeline.execute(
        CHAT_CAPABILITY_NAME,
        lambda resolved: asyncio.sleep(0, result=resolved),
    )
) is capability
assert pipeline.middleware == (middleware,)
assert len(middleware.invocations) == 1
assert middleware.invocations[0].capability_name == CHAT_CAPABILITY_NAME
assert middleware.invocations[0].capability is capability
assert middleware.invocations[0].streaming is False
assert CapabilityRegistrySealedError is not None
service_registry = RuntimeServiceRegistry()
assert service_registry.seal() == ()
assert service_registry.sealed is True
report = asyncio.run(RuntimeComponentHealthReporter(service_registry).report())
assert report.status is RuntimeComponentStatus.OK
assert report.components == ()
assert RuntimeServiceRegistrySealedError is not None
assert issubclass(ProviderError, TrussiumError)
assert ProviderError("safe").code == "provider_error"
PY
    )

    run_runtime "$environment" "$label"
}

run_runtime() {
    environment="$1"
    label="$2"
    python="$environment/bin/python"
    port="$($python -c \
        'import socket; sock = socket.socket(); sock.bind(("127.0.0.1", 0)); print(sock.getsockname()[1]); sock.close()')"
    request_id="package-smoke-65-$label"
    runtime_log="$work_directory/$label-runtime.log"

    TRUSSIUM_RUNTIME__HOST=127.0.0.1 \
        TRUSSIUM_RUNTIME__PORT="$port" \
        "$python" -m trussium >"$runtime_log" 2>&1 &
    runtime_pid="$!"

    attempt=0
    ready="false"
    while [ "$attempt" -lt 30 ]; do
        if ! kill -0 "$runtime_pid" >/dev/null 2>&1; then
            cat "$runtime_log" >&2
            fail "$label runtime exited before readiness"
        fi

        if "$python" - "$port" "$request_id" >/dev/null 2>&1 <<'PY'
import json
import sys
import urllib.request


port, request_id = sys.argv[1:]
for path in ("/health/live", "/health/ready"):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"X-Request-ID": request_id},
    )
    with urllib.request.urlopen(request, timeout=1) as response:
        assert response.status == 200
        assert json.load(response) == {"status": "ok"}
        assert response.headers["X-Request-ID"] == request_id

components_request = urllib.request.Request(
    f"http://127.0.0.1:{port}/health/components",
    headers={"X-Request-ID": request_id},
)
with urllib.request.urlopen(components_request, timeout=1) as response:
    assert response.status == 200
    assert json.load(response) == {"status": "ok", "components": []}
    assert response.headers["X-Request-ID"] == request_id

capabilities_request = urllib.request.Request(
    f"http://127.0.0.1:{port}/v1/capabilities",
    headers={"X-Request-ID": request_id},
)
with urllib.request.urlopen(capabilities_request, timeout=1) as response:
    assert response.status == 200
    assert json.load(response) == {"capabilities": []}
    assert response.headers["X-Request-ID"] == request_id

availability_request = urllib.request.Request(
    f"http://127.0.0.1:{port}/v1/capabilities/availability",
    headers={"X-Request-ID": request_id},
)
with urllib.request.urlopen(availability_request, timeout=1) as response:
    assert response.status == 200
    assert json.load(response) == {"status": "available", "capabilities": []}
    assert response.headers["X-Request-ID"] == request_id

health_request = urllib.request.Request(
    f"http://127.0.0.1:{port}/v1/capabilities/health",
    headers={"X-Request-ID": request_id},
)
with urllib.request.urlopen(health_request, timeout=1) as response:
    assert response.status == 200
    assert json.load(response) == {"status": "ok", "capabilities": []}
    assert response.headers["X-Request-ID"] == request_id

metrics_request = urllib.request.Request(
    f"http://127.0.0.1:{port}/metrics",
    headers={"X-Request-ID": request_id},
)
with urllib.request.urlopen(metrics_request, timeout=1) as response:
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/plain")
    assert response.headers["X-Request-ID"] == request_id
    metrics = response.read().decode()
    assert "python_info" in metrics
    assert "trussium_http_requests_active 0.0" in metrics
PY
        then
            ready="true"
            break
        fi

        attempt=$((attempt + 1))
        sleep 1
    done

    if [ "$ready" != "true" ]; then
        cat "$runtime_log" >&2
        fail "$label runtime did not become ready within 30 seconds"
    fi

    kill -TERM "$runtime_pid"
    attempt=0
    while kill -0 "$runtime_pid" >/dev/null 2>&1 && [ "$attempt" -lt 10 ]; do
        attempt=$((attempt + 1))
        sleep 1
    done

    if kill -0 "$runtime_pid" >/dev/null 2>&1; then
        kill -KILL "$runtime_pid" >/dev/null 2>&1 || true
        wait "$runtime_pid" >/dev/null 2>&1 || true
        runtime_pid=""
        cat "$runtime_log" >&2
        fail "$label runtime did not stop within 10 seconds"
    fi

    set +e
    wait "$runtime_pid"
    exit_code="$?"
    set -e
    runtime_pid=""

    case "$exit_code" in
        0)
            ;;
        143)
            grep -q "Application shutdown complete" "$runtime_log" || {
                cat "$runtime_log" >&2
                fail "$label runtime received SIGTERM without graceful shutdown"
            }
            ;;
        *)
            cat "$runtime_log" >&2
            fail "$label graceful shutdown returned exit code $exit_code"
            ;;
    esac

    grep -q '"event":"runtime.configuration.loaded"' "$runtime_log" || {
        cat "$runtime_log" >&2
        fail "$label runtime did not log loaded configuration"
    }
    grep -q '"event":"provider.configuration.unavailable"' "$runtime_log" || {
        cat "$runtime_log" >&2
        fail "$label runtime did not log unavailable provider configuration"
    }
    grep -q '"event":"runtime.started"' "$runtime_log" || {
        cat "$runtime_log" >&2
        fail "$label runtime did not log startup completion"
    }
    grep -q '"event":"runtime.shutdown.completed"' "$runtime_log" || {
        cat "$runtime_log" >&2
        fail "$label runtime did not log shutdown completion"
    }
}

validate_imports "$work_directory/wheel-environment" "$wheel" "wheel"
validate_imports "$work_directory/source-environment" "$source_distribution" "source"

echo "Package smoke test passed for Trussium $expected_version"
