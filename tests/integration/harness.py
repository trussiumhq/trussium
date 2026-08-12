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
_SHUTDOWN_TIMEOUT_SECONDS = 5.0


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

        self.send_sigterm()

        try:
            self.process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)

    def send_sigterm(self) -> None:
        """Deliver the production shutdown signal without waiting for exit."""
        self.process.terminate()

    def wait_for_exit(
        self,
        *,
        timeout_seconds: float = _SHUTDOWN_TIMEOUT_SECONDS,
    ) -> int:
        """Require the child to exit within a deterministic bound."""
        try:
            return self.process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            raise AssertionError(
                f"Process did not exit within {timeout_seconds} seconds.\n"
                f"Process output:\n{self.output()}"
            ) from error


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

    def operational_logs(
        self,
        *,
        event: str | None = None,
    ) -> list[dict[str, object]]:
        """Return runtime-owned structured operational records."""
        records: list[dict[str, object]] = []

        for line in self.runtime_process.output().splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict) or "event" not in payload:
                continue

            if event is None or payload.get("event") == event:
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

    def wait_for_operational_log(
        self,
        *,
        event: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, object]:
        """Wait until one process-level structured event is captured."""
        deadline = monotonic() + timeout_seconds

        while monotonic() < deadline:
            records = self.operational_logs(event=event)

            if records:
                return records[-1]

            sleep(0.02)

        raise AssertionError(
            f"Timed out waiting for operational event {event!r}.\n"
            f"Runtime output:\n{self.runtime_process.output()}"
        )

    def wait_for_provider_state(
        self,
        *,
        model: str,
        state: str,
        timeout_seconds: float = 5.0,
    ) -> dict[str, bool]:
        """Wait for a controlled fake-provider lifecycle transition."""
        deadline = monotonic() + timeout_seconds
        last_state: dict[str, bool] = {}

        with httpx.Client(timeout=0.5) as client:
            while monotonic() < deadline:
                response = client.get(
                    f"{self.fake_openai_url}/control/{model}",
                )
                response.raise_for_status()
                payload = response.json()
                last_state = payload["state"]

                if last_state.get(state) is True:
                    return last_state

                sleep(0.02)

        raise AssertionError(
            f"Timed out waiting for provider state {state!r} for {model!r}. "
            f"Last state: {last_state!r}.\n"
            f"Provider output:\n{self.fake_openai_process.output()}"
        )

    def wait_for_trace_exports(
        self,
        *,
        minimum_count: int,
        timeout_seconds: float = 5.0,
    ) -> list[dict[str, object]]:
        """Wait for the fake collector to receive OTLP trace payloads."""
        deadline = monotonic() + timeout_seconds
        exports: list[dict[str, object]] = []

        with httpx.Client(timeout=0.5) as client:
            while monotonic() < deadline:
                response = client.get(f"{self.fake_openai_url}/recorded-traces")
                response.raise_for_status()
                payload = response.json()
                exports = payload["exports"]

                if len(exports) >= minimum_count:
                    return exports

                sleep(0.02)

        raise AssertionError(
            f"Timed out waiting for {minimum_count} OTLP trace exports. "
            f"Last exports: {exports!r}.\n"
            f"Runtime output:\n{self.runtime_process.output()}"
        )

    def release_provider_workload(self, *, model: str) -> None:
        """Release a controlled fake-provider request or stream."""
        response = httpx.post(
            f"{self.fake_openai_url}/control/{model}/release",
            timeout=2,
        )
        response.raise_for_status()

    def wait_until_not_accepting_requests(
        self,
        *,
        timeout_seconds: float = 2.0,
    ) -> None:
        """Require the shutting-down runtime to close its listening socket."""
        deadline = monotonic() + timeout_seconds

        while monotonic() < deadline:
            try:
                httpx.get(
                    f"{self.base_url}/health/live",
                    headers={"Connection": "close"},
                    timeout=0.2,
                )
            except httpx.ConnectError:
                return
            except httpx.HTTPError:
                pass

            sleep(0.02)

        raise AssertionError(
            "Runtime continued accepting new connections after SIGTERM.\n"
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
    graceful_shutdown_seconds: int = 30,
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
            "TRUSSIUM_RUNTIME__GRACEFUL_SHUTDOWN_SECONDS": str(graceful_shutdown_seconds),
            "TRUSSIUM_TIMEOUTS__PROVIDER_REQUEST_SECONDS": "5",
            "TRUSSIUM_TIMEOUTS__STREAM_IDLE_SECONDS": "5",
            "TRUSSIUM_READINESS__DEPENDENCY_CHECKS_ENABLED": "true",
            "TRUSSIUM_READINESS__DEPENDENCY_TIMEOUT_SECONDS": "1",
            "TRUSSIUM_READINESS__DEPENDENCY_CACHE_SECONDS": "0.1",
            "TRUSSIUM_READINESS__REQUIRED_MODEL": "e2e-model",
            "TRUSSIUM_OBSERVABILITY__TRACING_ENABLED": "true",
            "TRUSSIUM_OBSERVABILITY__TRACING_SERVICE_NAME": "trussium-integration",
            "TRUSSIUM_OBSERVABILITY__OTLP_TRACES_ENDPOINT": (f"{fake_openai_url}/v1/traces"),
            "TRUSSIUM_OBSERVABILITY__OTLP_EXPORT_TIMEOUT_SECONDS": "2",
            "OTEL_BSP_SCHEDULE_DELAY": "50",
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
