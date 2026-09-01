"""Local workflow admission and graceful-drain lifecycle."""

import asyncio
from enum import StrEnum
from math import isfinite

from trussium.workflows.policy import WorkflowAdmissionError


class WorkflowLifecycleState(StrEnum):
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"


class WorkflowLifecycle:
    """Track active workflows and provide bounded shutdown admission."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._drained = asyncio.Event()
        self._drained.set()
        self._active = 0
        self._state = WorkflowLifecycleState.RUNNING

    @property
    def active_count(self) -> int:
        return self._active

    @property
    def state(self) -> WorkflowLifecycleState:
        return self._state

    async def admit(self) -> None:
        async with self._lock:
            if self._state is not WorkflowLifecycleState.RUNNING:
                raise WorkflowAdmissionError(
                    "workflow_runtime_draining", "Workflow runtime is draining."
                )
            self._active += 1
            self._drained.clear()

    async def release(self) -> None:
        async with self._lock:
            if self._active == 0:
                raise RuntimeError("Workflow release without an active execution")
            self._active -= 1
            if self._active == 0:
                self._drained.set()

    async def begin_shutdown(self) -> None:
        async with self._lock:
            if self._state is WorkflowLifecycleState.RUNNING:
                self._state = WorkflowLifecycleState.DRAINING
            if self._active == 0:
                self._state = WorkflowLifecycleState.STOPPED
                self._drained.set()

    async def drain(self, timeout_seconds: float) -> bool:
        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Workflow drain timeout must be finite and positive")
        await self.begin_shutdown()
        try:
            async with asyncio.timeout(timeout_seconds):
                await self._drained.wait()
        except TimeoutError:
            return False
        async with self._lock:
            self._state = WorkflowLifecycleState.STOPPED
        return True
