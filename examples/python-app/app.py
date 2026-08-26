"""Small application example that calls an existing Trussium runtime."""

import os
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from trussium_sdk import APIError, TrussiumClient


class AskRequest(BaseModel):
    """Application input for one non-streaming completion."""

    prompt: str
    model: str | None = None


app = FastAPI(title="Trussium example application")


def runtime_url() -> str:
    """Return the configured runtime URL."""
    return os.getenv("TRUSSIUM_URL", "http://127.0.0.1:9000")


def configured_model() -> str:
    """Return the default model configured for this application."""
    return os.getenv("TRUSSIUM_MODEL", "llama3.1:8b")


def correlation_id(request_id: str | None) -> str:
    """Preserve a caller ID or create a bounded application correlation ID."""
    return request_id or f"example-{uuid4()}"


@app.get("/health")
def health() -> dict[str, object]:
    """Report whether the configured Trussium runtime is traffic-ready."""
    try:
        with TrussiumClient(runtime_url()) as client:
            return client.readiness()
    except (APIError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="Trussium runtime is unavailable") from error


@app.get("/capabilities")
def capabilities() -> dict[str, object]:
    """Return public capability metadata from the configured runtime."""
    try:
        with TrussiumClient(runtime_url()) as client:
            return client.capabilities()
    except (APIError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="Trussium runtime is unavailable") from error


@app.post("/ask")
def ask(
    request: AskRequest,
    x_request_id: str | None = Header(default=None),
) -> dict[str, object]:
    """Submit one prompt while preserving request correlation."""
    try:
        with TrussiumClient(runtime_url()) as client:
            return client.complete(
                {
                    "model": request.model or configured_model(),
                    "messages": [{"role": "user", "content": request.prompt}],
                },
                request_id=correlation_id(x_request_id),
            )
    except APIError as error:
        raise HTTPException(status_code=502, detail=error.code or "runtime_error") from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Trussium runtime is unavailable") from error
