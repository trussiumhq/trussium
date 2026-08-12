"""Production ASGI server lifecycle."""

import asyncio
import logging
import socket
from time import perf_counter
from typing import Final

import uvicorn
from starlette.types import ASGIApp

from trussium.config.settings import RuntimeSettings
from trussium.observability.logging import get_logger
from trussium.observability.operations import (
    RUNTIME_SHUTDOWN_CLEANUP_TIMEOUT,
    RUNTIME_SHUTDOWN_COMPLETED,
    RUNTIME_SHUTDOWN_DRAIN_TIMEOUT,
    RUNTIME_SHUTDOWN_STARTED,
)

CANCELLATION_CLEANUP_SECONDS: Final = 1.0


class GracefulShutdownServer(uvicorn.Server):
    """Uvicorn server that waits briefly for cancelled request cleanup."""

    async def shutdown(
        self,
        sockets: list[socket.socket] | None = None,
    ) -> None:
        """Drain requests, then bound cooperative cancellation cleanup."""
        shutdown_started_at = perf_counter()
        drain_timed_out = False
        uvicorn_logger = logging.getLogger("uvicorn.error")
        runtime_logger = get_logger("runtime")
        uvicorn_logger.info("Shutting down")
        runtime_logger.info(
            "Runtime shutdown started",
            extra={
                "event": RUNTIME_SHUTDOWN_STARTED,
                "active_tasks": len(self.server_state.tasks),
                "graceful_shutdown_seconds": self.config.timeout_graceful_shutdown,
            },
        )

        for server in self.servers:
            server.close()

        for configured_socket in sockets or []:
            configured_socket.close()

        for connection in list(self.server_state.connections):
            connection.shutdown()

        await asyncio.sleep(0.1)

        try:
            await asyncio.wait_for(
                self._wait_tasks_to_complete(),
                timeout=self.config.timeout_graceful_shutdown,
            )
        except TimeoutError:
            drain_timed_out = True
            cancelled_tasks = tuple(self.server_state.tasks)
            uvicorn_logger.error(
                "Cancel %s running task(s), timeout graceful shutdown exceeded",
                len(cancelled_tasks),
            )
            runtime_logger.error(
                "Runtime request drain timed out",
                extra={
                    "event": RUNTIME_SHUTDOWN_DRAIN_TIMEOUT,
                    "error_code": "graceful_shutdown_timeout",
                    "active_tasks": len(cancelled_tasks),
                    "graceful_shutdown_seconds": self.config.timeout_graceful_shutdown,
                },
            )

            for task in cancelled_tasks:
                task.cancel(
                    msg="Task cancelled, timeout graceful shutdown exceeded",
                )

            if cancelled_tasks:
                _, unfinished_tasks = await asyncio.wait(
                    cancelled_tasks,
                    timeout=CANCELLATION_CLEANUP_SECONDS,
                )

                if unfinished_tasks:
                    uvicorn_logger.warning(
                        "%s cancelled request cleanup task(s) exceeded %.1f seconds",
                        len(unfinished_tasks),
                        CANCELLATION_CLEANUP_SECONDS,
                    )
                    runtime_logger.warning(
                        "Cancelled request cleanup timed out",
                        extra={
                            "event": RUNTIME_SHUTDOWN_CLEANUP_TIMEOUT,
                            "error_code": "cancellation_cleanup_timeout",
                            "unfinished_tasks": len(unfinished_tasks),
                            "cleanup_timeout_seconds": CANCELLATION_CLEANUP_SECONDS,
                        },
                    )

        try:
            if not self.force_exit:
                await self.lifespan.shutdown()
        except Exception as error:
            runtime_logger.error(
                "Runtime shutdown completed with an operational failure",
                extra={
                    "event": RUNTIME_SHUTDOWN_COMPLETED,
                    "duration_ms": round((perf_counter() - shutdown_started_at) * 1000, 3),
                    "error_code": "runtime_shutdown_failed",
                    "error_type": type(error).__name__,
                    "outcome": "failed",
                },
            )
            raise

        runtime_logger.info(
            "Runtime shutdown completed",
            extra={
                "event": RUNTIME_SHUTDOWN_COMPLETED,
                "duration_ms": round((perf_counter() - shutdown_started_at) * 1000, 3),
                "outcome": "forced" if drain_timed_out or self.force_exit else "completed",
            },
        )


def create_server(
    application: ASGIApp,
    *,
    settings: RuntimeSettings,
) -> GracefulShutdownServer:
    """Create the configured production server."""
    config = uvicorn.Config(
        app=application,
        host=settings.host,
        port=settings.port,
        timeout_graceful_shutdown=settings.graceful_shutdown_seconds,
    )
    return GracefulShutdownServer(config)
