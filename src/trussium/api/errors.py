"""HTTP mappings and bounded API error responses."""

from collections.abc import Sequence
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from trussium.capabilities.errors import CapabilityErrorCategory


class APIError(BaseModel):
    """Stable, client-safe error detail shared by runtime and validation errors."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    fields: tuple[str, ...] = ()


class APIErrorResponse(BaseModel):
    """Consistent HTTP error envelope."""

    model_config = ConfigDict(frozen=True)

    detail: APIError


async def request_validation_exception_handler(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    """Normalize request validation failures without echoing input values."""
    fields = tuple(_location_label(item.get("loc", ())) for item in error.errors())
    payload = APIErrorResponse(
        detail=APIError(
            code="validation_error",
            message="Request validation failed.",
            fields=fields,
        )
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=payload.model_dump(),
    )


def _location_label(location: Sequence[Any]) -> str:
    """Return a bounded field path without exposing rejected values."""
    parts = [str(part) for part in location if part not in {"body", "query", "path", "header"}]
    return ".".join(parts)[:128] or "request"


def capability_error_status_code(
    category: CapabilityErrorCategory,
) -> int:
    """Map a protocol-neutral capability category to an HTTP status.

    Args:
        category: Normalized capability error category.

    Returns:
        HTTP status code appropriate for the REST API.

    Raises:
        ValueError: If the category has no HTTP mapping.
    """
    match category:
        case CapabilityErrorCategory.INVALID_REQUEST:
            return status.HTTP_400_BAD_REQUEST

        case CapabilityErrorCategory.RATE_LIMITED:
            return status.HTTP_429_TOO_MANY_REQUESTS

        case CapabilityErrorCategory.QUOTA_EXCEEDED:
            return status.HTTP_503_SERVICE_UNAVAILABLE

        case CapabilityErrorCategory.UPSTREAM_TIMEOUT:
            return status.HTTP_504_GATEWAY_TIMEOUT

        case (
            CapabilityErrorCategory.UPSTREAM_AUTHENTICATION
            | CapabilityErrorCategory.UPSTREAM_PERMISSION
            | CapabilityErrorCategory.UPSTREAM_CONNECTION
            | CapabilityErrorCategory.UPSTREAM_FAILURE
        ):
            return status.HTTP_502_BAD_GATEWAY

    raise ValueError(f"Unsupported capability error category: {category}")


__all__ = [
    "APIError",
    "APIErrorResponse",
    "capability_error_status_code",
    "request_validation_exception_handler",
]
