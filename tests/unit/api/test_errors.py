"""Tests for capability error HTTP mappings."""

import pytest
from fastapi import status

from trussium.api.errors import capability_error_status_code
from trussium.capabilities.errors import CapabilityErrorCategory


@pytest.mark.parametrize(
    ("category", "expected_status"),
    [
        (
            CapabilityErrorCategory.INVALID_REQUEST,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            CapabilityErrorCategory.RATE_LIMITED,
            status.HTTP_429_TOO_MANY_REQUESTS,
        ),
        (
            CapabilityErrorCategory.QUOTA_EXCEEDED,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            CapabilityErrorCategory.UPSTREAM_AUTHENTICATION,
            status.HTTP_502_BAD_GATEWAY,
        ),
        (
            CapabilityErrorCategory.UPSTREAM_PERMISSION,
            status.HTTP_502_BAD_GATEWAY,
        ),
        (
            CapabilityErrorCategory.UPSTREAM_TIMEOUT,
            status.HTTP_504_GATEWAY_TIMEOUT,
        ),
        (
            CapabilityErrorCategory.UPSTREAM_CONNECTION,
            status.HTTP_502_BAD_GATEWAY,
        ),
        (
            CapabilityErrorCategory.UPSTREAM_FAILURE,
            status.HTTP_502_BAD_GATEWAY,
        ),
    ],
)
def test_capability_error_category_maps_to_http_status(
    category: CapabilityErrorCategory,
    expected_status: int,
) -> None:
    """Every capability error category should have an HTTP mapping."""
    assert capability_error_status_code(category) == expected_status
