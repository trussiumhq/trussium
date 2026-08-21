"""Command-line interface for the Trussium runtime."""

import argparse
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from trussium import __version__
from trussium.__main__ import main as serve_runtime
from trussium.config.settings import get_settings


def main(arguments: Sequence[str] | None = None) -> None:
    """Run the Trussium command-line interface."""
    parser = argparse.ArgumentParser(prog="trussium")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    config = commands.add_parser("config")
    config.add_subparsers(dest="config_command", required=True).add_parser("validate")
    health = commands.add_parser("health")
    health.add_argument("--url", default="http://127.0.0.1:9000")
    commands.add_parser("version")
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
