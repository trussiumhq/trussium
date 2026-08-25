"""Keep core SDK links aligned with the dedicated repositories."""

from pathlib import Path


def test_sdk_guides_reference_published_packages() -> None:
    readme = Path("README.md").read_text()
    python = Path("docs/PYTHON_SDK.md").read_text()
    go = Path("docs/GO_SDK.md").read_text()
    typescript = Path("docs/TYPESCRIPT_SDK.md").read_text()

    assert "trussium-sdk" in readme
    assert "github.com/trussiumhq/trussium-go" in readme
    assert "github.com/trussiumhq/trussium-python" in python
    assert "examples/basic.py" in python
    assert "TRUSSIUM_URL" in python
    assert "github.com/trussiumhq/trussium-go/blob/main/examples/basic/main.go" in go
    assert "examples/basic/main.go" in go
    assert "TRUSSIUM_URL" in go
    assert "@trussium/sdk" in readme
    assert "@trussium/sdk" in typescript
    assert "npm publication is deferred" in typescript
    assert "npm run build" in typescript
    assert "examples/basic.ts" in typescript
    assert "TRUSSIUM_URL" in typescript
    assert "multipart" in typescript
    assert "transcription" in typescript
    assert "batch jobs" in typescript
