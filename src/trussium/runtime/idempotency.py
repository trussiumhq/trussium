"""Bounded process-local idempotency for completed requests."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import TypeVar, cast

ResultT = TypeVar("ResultT")


class IdempotencyConflictError(ValueError):
    """Raised when a key is reused with a different request fingerprint."""


class IdempotencyStore:
    """Cache successful results for bounded, process-local replay protection."""

    def __init__(self, *, ttl_seconds: float = 300.0, max_entries: int = 1024) -> None:
        if ttl_seconds <= 0 or max_entries < 1:
            raise ValueError("Idempotency TTL and entry limit must be positive")
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[str, tuple[str, float, object]] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        key: str,
        request: object,
        operation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        """Replay a matching successful result or execute and cache it."""
        fingerprint = hashlib.sha256(
            json.dumps(request, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        async with self._lock:
            now = monotonic()
            self._entries = {k: v for k, v in self._entries.items() if v[1] > now}
            existing = self._entries.get(key)
            if existing is not None:
                if existing[0] != fingerprint:
                    raise IdempotencyConflictError("Idempotency key was reused for another request")
                return cast(ResultT, existing[2])
        result = await operation()
        async with self._lock:
            if len(self._entries) >= self._max_entries:
                self._entries.pop(next(iter(self._entries)))
            self._entries[key] = (fingerprint, monotonic() + self._ttl, result)
        return result


__all__ = ["IdempotencyConflictError", "IdempotencyStore"]
