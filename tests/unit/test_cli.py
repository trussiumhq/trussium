"""Tests for the runtime CLI."""

import pytest

from trussium import __version__
from trussium.cli import main


def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(("version",))
    assert capsys.readouterr().out == f"{__version__}\n"


def test_configuration_validation_reports_success(capsys: pytest.CaptureFixture[str]) -> None:
    main(("config", "validate"))
    assert capsys.readouterr().out == "Configuration is valid.\n"
