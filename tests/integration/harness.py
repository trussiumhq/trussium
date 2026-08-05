"""Reusable process and network harness for integration tests."""

import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep

import httpx

_STARTUP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class ManagedProcess:
    """A child process with captured combined output."""

    process: subprocess.Popen[str]
    log_path: Path

    def output(self) -> str:
        """Return all output currently captured from the child."""
        if not self.log_path.exists():
            return ""

        return self.log_path.read_text(encoding="utf-8")

    def stop(self) -> None:
        """Terminate the child and escalate to kill after a bounded wait."""
        if self.process.poll() is not None:
            return

        self.process.terminate()

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


@dataclass(frozen=True)
class IntegrationRuntime:
    """Addresses and logs for a running end-to-end test environment."""

    base_url: str
    fake_openai_url: str
    runtime_process: ManagedProcess
    fake_openai_process: ManagedProcess

    def structured_logs(
        self,
        *,
        request_id: str,
    ) -> list[dict[str, object]]:
        """Return structured runtime logs for one correlated request."""
        records: list[dict[str, object]] = []

        for line in self.runtime_process.output().splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(payload, dict) and payload.get("request_id") == request_id:
                records.append(payload)

        return records

    def wait_for_terminal_log(
        self,
        *,
        request_id: str,
        event: str,
    ) -> list[dict[str, object]]:
        """Wait until a request's terminal structured event is captured."""
        deadline = monotonic() + 5

        while monotonic() < deadline:
            records = self.structured_logs(request_id=request_id)

            if any(record.get("event") == event for record in records):
                return records

            sleep(0.02)

        raise AssertionError(
            f"Timed out waiting for {event!r} for {request_id!r}.\n"
            f"Runtime output:\n{self.runtime_process.output()}"
        )


def reserve_loopback_port() -> int:
    """Ask the operating system for an available loopback TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def start_process(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    log_path: Path,
) -> ManagedProcess:
    """Start a child process with output captured to a file."""
    with log_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )

    return ManagedProcess(
        process=process,
        log_path=log_path,
    )


def wait_until_ready(
    url: str,
    *,
    process: ManagedProcess,
) -> None:
    """Poll a readiness URL until it succeeds or the child fails."""
    deadline = monotonic() + _STARTUP_TIMEOUT_SECONDS
    last_error: Exception | None = None

    with httpx.Client(timeout=0.25) as client:
        while monotonic() < deadline:
            return_code = process.process.poll()

            if return_code is not None:
                raise AssertionError(
                    f"Process exited with code {return_code} before {url} was ready.\n"
                    f"Process output:\n{process.output()}"
                )

            try:
                response = client.get(url)
                response.raise_for_status()
                return
            except httpx.HTTPError as error:
                last_error = error
                sleep(0.05)

    raise AssertionError(
        f"Timed out waiting for {url}: {last_error!r}.\nProcess output:\n{process.output()}"
    )


def create_integration_runtime(
    *,
    repository_root: Path,
    log_directory: Path,
    provider_name: str = "openai",
) -> IntegrationRuntime:
    """Start a compatible fake API and production Trussium entry point."""
    fake_openai_port = reserve_loopback_port()
    runtime_port = reserve_loopback_port()
    fake_openai_url = f"http://127.0.0.1:{fake_openai_port}"
    base_url = f"http://127.0.0.1:{runtime_port}"
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"

    fake_openai_process = start_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.integration.fake_openai:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(fake_openai_port),
            "--log-level",
            "warning",
        ],
        cwd=repository_root,
        environment=environment,
        log_path=log_directory / "fake-openai.log",
    )

    try:
        wait_until_ready(
            f"{fake_openai_url}/health",
            process=fake_openai_process,
        )
    except Exception:
        fake_openai_process.stop()
        raise

    runtime_environment = environment.copy()
    runtime_environment.update(
        {
            "TRUSSIUM_RUNTIME__HOST": "127.0.0.1",
            "TRUSSIUM_RUNTIME__PORT": str(runtime_port),
            "TRUSSIUM_TIMEOUTS__PROVIDER_REQUEST_SECONDS": "5",
            "TRUSSIUM_TIMEOUTS__STREAM_IDLE_SECONDS": "5",
        }
    )

    if provider_name == "openai":
        runtime_environment.update(
            {
                "OPENAI_API_KEY": "e2e-test-api-key",
                "OPENAI_BASE_URL": f"{fake_openai_url}/v1",
            }
        )
    else:
        runtime_environment.update(
            {
                "TRUSSIUM_PROVIDER__NAME": provider_name,
                "TRUSSIUM_PROVIDER__BASE_URL": f"{fake_openai_url}/v1",
                "TRUSSIUM_PROVIDER__API_KEY": "e2e-test-api-key",
            }
        )
    runtime_process = start_process(
        [
            sys.executable,
            "-m",
            "trussium",
        ],
        cwd=repository_root,
        environment=runtime_environment,
        log_path=log_directory / "trussium.log",
    )

    try:
        wait_until_ready(
            f"{base_url}/health/ready",
            process=runtime_process,
        )
    except Exception:
        runtime_process.stop()
        fake_openai_process.stop()
        raise

    return IntegrationRuntime(
        base_url=base_url,
        fake_openai_url=fake_openai_url,
        runtime_process=runtime_process,
        fake_openai_process=fake_openai_process,
    )
