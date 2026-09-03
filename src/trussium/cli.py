"""Command-line interface for the Trussium runtime."""

import argparse
import json
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from trussium import __version__
from trussium.__main__ import main as serve_runtime
from trussium.config.settings import get_settings


def main(arguments: Sequence[str] | None = None) -> None:
    """Run the Trussium command-line interface."""
    parser = argparse.ArgumentParser(
        prog="trussium",
        description="Operate a Trussium runtime.",
        epilog="Runtime and Kubernetes administration are intentionally separate concerns.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="print the installed runtime version and exit",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="start the runtime server")
    config = commands.add_parser("config", help="inspect runtime configuration")
    config_subcommands = config.add_subparsers(dest="config_command", required=True)
    config_subcommands.add_parser("validate", help="validate settings without starting the server")
    health = commands.add_parser("health", help="check runtime readiness")
    health.add_argument("--url", default="http://127.0.0.1:9000", help="runtime base URL")
    capabilities = commands.add_parser(
        "capabilities", help="list publicly advertised capability metadata"
    )
    capabilities.add_argument("--url", default="http://127.0.0.1:9000", help="runtime base URL")
    diagnostics = commands.add_parser(
        "diagnostics", help="collect bounded runtime, provider, and capability health"
    )
    diagnostics.add_argument("--url", default="http://127.0.0.1:9000", help="runtime base URL")
    diagnostics.add_argument(
        "--provider", help="limit the provider health report to one provider name"
    )
    diagnostics.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="output format (default: json)",
    )
    commands.add_parser("version", help="print the installed runtime version")
    parsed = parser.parse_args(arguments)

    if parsed.command == "serve":
        serve_runtime()
        return
    if parsed.command == "config":
        _validate_configuration()
        return
    if parsed.command == "health":
        _health(parsed.url)
        return
    if parsed.command == "capabilities":
        _capabilities(parsed.url)
        return
    if parsed.command == "diagnostics":
        _diagnostics(parsed.url, provider=parsed.provider, output_format=parsed.format)
        return
    print(__version__)


def _validate_configuration() -> None:
    try:
        get_settings()
    except ValidationError:
        raise SystemExit(2) from None
    print("Configuration is valid.")


def _health(url: str) -> None:
    try:
        response = httpx.get(f"{url.rstrip('/')}/health/ready", timeout=5)
        response.raise_for_status()
    except httpx.HTTPError:
        raise SystemExit(1) from None
    print("Runtime is ready.")


def _capabilities(url: str) -> None:
    try:
        response = httpx.get(f"{url.rstrip('/')}/v1/capabilities", timeout=5)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise SystemExit(1) from None
    print(json.dumps(payload, sort_keys=True))


def _diagnostics(url: str, *, provider: str | None = None, output_format: str = "json") -> None:
    """Print bounded health reports without exposing runtime configuration."""
    base_url = url.rstrip("/")
    endpoints = {
        "readiness": "/health/ready",
        "components": "/health/components",
        "providers": "/v1/providers/health",
        "capabilities": "/v1/capabilities/availability",
    }
    reports: dict[str, object] = {}
    failed = False
    for name, path in endpoints.items():
        try:
            response = httpx.get(f"{base_url}{path}", timeout=5)
            response.raise_for_status()
            payload = response.json()
            if name == "providers" and provider is not None:
                payload = _filter_provider_report(payload, provider)
            reports[name] = payload
        except (httpx.HTTPError, ValueError):
            reports[name] = {"status": "unavailable"}
            failed = True
    if output_format == "text":
        for name, report in reports.items():
            status = (
                report.get("status", "unavailable") if isinstance(report, dict) else "unavailable"
            )
            print(f"{name}: {status}")
    else:
        print(json.dumps(reports, sort_keys=True))
    if failed:
        raise SystemExit(1)


def _filter_provider_report(payload: object, provider: str) -> object:
    """Filter a provider report while preserving the bounded response shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("providers"), list):
        return payload
    return {
        **payload,
        "providers": [
            item
            for item in payload["providers"]
            if isinstance(item, dict) and item.get("name") == provider
        ],
    }
