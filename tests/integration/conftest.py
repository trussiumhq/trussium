"""Pytest fixtures for end-to-end runtime integration tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.harness import (
    IntegrationRuntime,
    create_integration_runtime,
)


@pytest.fixture(scope="session")
def integration_runtime(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[IntegrationRuntime]:
    """Run production Trussium against the deterministic fake provider."""
    repository_root = Path(__file__).resolve().parents[2]
    log_directory = tmp_path_factory.mktemp("integration-process-logs")
    runtime = create_integration_runtime(
        repository_root=repository_root,
        log_directory=log_directory,
    )

    try:
        yield runtime
    finally:
        runtime.runtime_process.stop()
        runtime.fake_openai_process.stop()
