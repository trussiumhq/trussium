"""Production ASGI server lifecycle."""

import asyncio
import logging
import socket
from typing import Final

import uvicorn
from starlette.types import ASGIApp

from trussium.config.settings import RuntimeSettings

CANCELLATION_CLEANUP_SECONDS: Final = 1.0


class GracefulShutdownServer(uvicorn.Server):
    """Uvicorn server that waits briefly for cancelled request cleanup."""

    async def shutdown(
        self,
        sockets: list[socket.socket] | None = None,
    ) -> None:
        """Drain requests, then bound cooperative cancellation cleanup."""
        logger = logging.getLogger("uvicorn.error")
        logger.info("Shutting down")

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
            cancelled_tasks = tuple(self.server_state.tasks)
            logger.error(
                "Cancel %s running task(s), timeout graceful shutdown exceeded",
                len(cancelled_tasks),
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
                    logger.warning(
                        "%s cancelled request cleanup task(s) exceeded %.1f seconds",
                        len(unfinished_tasks),
                        CANCELLATION_CLEANUP_SECONDS,
                    )

        if not self.force_exit:
            await self.lifespan.shutdown()


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
