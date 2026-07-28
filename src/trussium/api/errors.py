"""HTTP mappings for normalized capability errors."""

from fastapi import status

from trussium.capabilities.errors import CapabilityErrorCategory


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
