"""Tests for request-correlation middleware."""

import asyncio
from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.middleware import (
    REQUEST_ID_HEADER,
    RequestCorrelationMiddleware,
)
from trussium.runtime import get_request_id


def create_test_application() -> FastAPI:
    """Create an application with request-correlation middleware."""
    application = FastAPI()

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    @application.get("/context")
    async def read_context() -> dict[str, str | None]:
        """Return the active request identifier."""
        return {
            "request_id": get_request_id(),
        }

    @application.get("/error")
    async def raise_error() -> None:
        """Raise a test HTTP error."""
        raise HTTPException(
            status_code=status.HTTP_418_IM_A_TEAPOT,
            detail="Test error.",
        )

    @application.get("/stream")
    async def stream_context() -> StreamingResponse:
        """Return request-context values from a stream."""

        async def generate() -> AsyncIterator[str]:
            first_request_id = get_request_id()

            await asyncio.sleep(0)

            second_request_id = get_request_id()

            yield f"{first_request_id}|{second_request_id}"

        return StreamingResponse(
            content=generate(),
            media_type="text/plain",
        )

    return application


def test_supplied_request_id_is_preserved() -> None:
    """A caller-provided request identifier should be preserved."""
    client = TestClient(create_test_application())

    response = client.get(
        "/context",
        headers={
            REQUEST_ID_HEADER: "trussium-test-123",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers[REQUEST_ID_HEADER] == "trussium-test-123"
    assert response.json() == {
        "request_id": "trussium-test-123",
    }


def test_request_id_is_generated_when_missing() -> None:
    """A UUID should be generated when the header is missing."""
    client = TestClient(create_test_application())

    response = client.get("/context")

    assert response.status_code == status.HTTP_200_OK

    request_id = response.headers[REQUEST_ID_HEADER]

    assert str(UUID(request_id)) == request_id
    assert response.json() == {
        "request_id": request_id,
    }


def test_request_id_is_generated_when_header_is_empty() -> None:
    """A UUID should be generated for an empty request header."""
    client = TestClient(create_test_application())

    response = client.get(
        "/context",
        headers={
            REQUEST_ID_HEADER: "",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    request_id = response.headers[REQUEST_ID_HEADER]

    assert str(UUID(request_id)) == request_id
    assert response.json() == {
        "request_id": request_id,
    }


def test_error_response_contains_request_id() -> None:
    """HTTP errors should contain the active request identifier."""
    client = TestClient(create_test_application())

    response = client.get(
        "/error",
        headers={
            REQUEST_ID_HEADER: "trussium-error-123",
        },
    )

    assert response.status_code == status.HTTP_418_IM_A_TEAPOT
    assert response.headers[REQUEST_ID_HEADER] == "trussium-error-123"
    assert response.json() == {
        "detail": "Test error.",
    }


def test_request_context_remains_available_during_streaming() -> None:
    """The request identifier should remain active during streaming."""
    client = TestClient(create_test_application())

    with client.stream(
        "GET",
        "/stream",
        headers={
            REQUEST_ID_HEADER: "trussium-stream-123",
        },
    ) as response:
        body = "".join(response.iter_text())

        assert response.status_code == status.HTTP_200_OK
        assert response.headers[REQUEST_ID_HEADER] == "trussium-stream-123"

    assert body == "trussium-stream-123|trussium-stream-123"


def test_application_factory_registers_request_id_middleware() -> None:
    """The application factory should install the middleware."""
    application = create_application(
        chat_capability=None,
    )

    middleware_classes = {
        cast(object, middleware.cls) for middleware in application.user_middleware
    }

    assert RequestCorrelationMiddleware in middleware_classes


def test_health_response_contains_generated_request_id() -> None:
    """Health responses should contain generated request identifiers."""
    application = create_application(
        chat_capability=None,
    )
    client = TestClient(application)

    response = client.get("/health/live")

    assert response.status_code == status.HTTP_200_OK

    request_id = response.headers[REQUEST_ID_HEADER]

    assert str(UUID(request_id)) == request_id


def test_request_context_is_not_active_outside_request() -> None:
    """Request context should not leak outside request handling."""
    client = TestClient(create_test_application())

    response = client.get(
        "/context",
        headers={
            REQUEST_ID_HEADER: "trussium-context-123",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert get_request_id() is None
