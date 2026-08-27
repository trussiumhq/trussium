"""Shared validation types for normalized capability requests."""

from typing import Annotated

from pydantic import StringConstraints

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
"""A stripped, non-empty public request string."""

__all__ = ["NonBlankString"]
