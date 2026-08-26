"""Keep the complete example application aligned with SDK boundaries."""

from pathlib import Path

EXAMPLE = Path("examples/python-app")


def test_example_application_has_runnable_self_hosted_contract() -> None:
    app = (EXAMPLE / "app.py").read_text()
    readme = (EXAMPLE / "README.md").read_text()
    package = (EXAMPLE / "pyproject.toml").read_text()

    for marker in ("FastAPI", "TrussiumClient", "/health", "/capabilities", "/ask", "x_request_id"):
        assert marker in app
    assert "trussium-sdk" in package
    assert "uv run uvicorn app:app" in readme
    assert "does not install, host, or configure Trussium" in readme
