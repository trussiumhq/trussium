"""Tests for the runtime CLI."""

import httpx
import pytest

from trussium import __version__
from trussium.cli import main


def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(("version",))
    assert capsys.readouterr().out == f"{__version__}\n"


def test_version_option_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(("--version",))
    assert capsys.readouterr().out == f"{__version__}\n"


def test_help_describes_runtime_scope(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(("--help",))
    output = capsys.readouterr().out
    assert "Operate a Trussium runtime." in output
    assert "Runtime and Kubernetes administration" in output
    assert "capabilities" in output


def test_configuration_validation_reports_success(capsys: pytest.CaptureFixture[str]) -> None:
    main(("config", "validate"))
    assert capsys.readouterr().out == "Configuration is valid.\n"


def test_capabilities_prints_stable_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def get(url: str, *, timeout: float) -> httpx.Response:
        assert url == "http://runtime.test/v1/capabilities"
        assert timeout == 5
        return httpx.Response(
            200,
            json={"capabilities": [{"name": "chat.completions"}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("trussium.cli.httpx.get", get)
    main(("capabilities", "--url", "http://runtime.test/"))
    assert capsys.readouterr().out == '{"capabilities": [{"name": "chat.completions"}]}\n'


def test_capabilities_exits_one_on_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def get(_: str, *, timeout: float) -> httpx.Response:
        del timeout
        return httpx.Response(503, request=httpx.Request("GET", "http://runtime.test"))

    monkeypatch.setattr("trussium.cli.httpx.get", get)
    with pytest.raises(SystemExit, match="1"):
        main(("capabilities", "--url", "http://runtime.test"))


def test_diagnostics_collects_bounded_reports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    reports = {
        "/health/ready": {"status": "ok"},
        "/health/components": {"status": "ok", "components": []},
        "/v1/providers/health": {
            "status": "ok",
            "providers": [{"name": "openai", "status": "ok"}, {"name": "ollama", "status": "ok"}],
        },
        "/v1/capabilities/availability": {"status": "ok", "capabilities": []},
    }

    def get(url: str, *, timeout: float) -> httpx.Response:
        assert timeout == 5
        path = "/" + url.split("/", 3)[-1]
        return httpx.Response(200, json=reports[path], request=httpx.Request("GET", url))

    monkeypatch.setattr("trussium.cli.httpx.get", get)
    main(("diagnostics", "--url", "http://runtime.test/", "--provider", "openai"))
    assert capsys.readouterr().out == (
        '{"capabilities": {"capabilities": [], "status": "ok"}, '
        '"components": {"components": [], "status": "ok"}, '
        '"providers": {"providers": [{"name": "openai", "status": "ok"}], "status": "ok"}, '
        '"readiness": {"status": "ok"}}\n'
    )


def test_diagnostics_text_format_prints_statuses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def get(url: str, *, timeout: float) -> httpx.Response:
        del timeout
        payload = {"status": "ok"}
        if url.endswith("/health/components"):
            payload = {"status": "degraded"}
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr("trussium.cli.httpx.get", get)
    main(("diagnostics", "--url", "http://runtime.test", "--format", "text"))
    assert capsys.readouterr().out == (
        "readiness: ok\ncomponents: degraded\nproviders: ok\ncapabilities: ok\n"
    )


def test_diagnostics_text_includes_provider_details(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def get(url: str, *, timeout: float) -> httpx.Response:
        del timeout
        payload: object = {"status": "ok"}
        if url.endswith("/v1/providers/health"):
            payload = {
                "status": "degraded",
                "providers": [{"name": "ollama", "status": "unavailable", "reason": "timeout"}],
            }
        elif url.endswith("/v1/capabilities/availability"):
            payload = {
                "status": "available",
                "capabilities": [{"name": "chat.completions", "status": "available"}],
            }
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr("trussium.cli.httpx.get", get)
    main(("diagnostics", "--url", "http://runtime.test", "--format", "text"))
    output = capsys.readouterr().out
    assert "providers: degraded\n  ollama: unavailable (timeout)\n" in output
    assert "capabilities: available\n  chat.completions: available\n" in output
