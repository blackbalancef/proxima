from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable, Coroutine
from typing import Any

ShutdownCallback = Callable[[], Coroutine[Any, Any, None]]

_shutdown_callback: ShutdownCallback | None = None
_restart_requested: bool = False


def setup_signal_handlers(shutdown_cb: ShutdownCallback) -> None:
    global _shutdown_callback  # noqa: PLW0603
    _shutdown_callback = shutdown_cb
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown_cb()))


async def request_restart() -> None:
    global _restart_requested  # noqa: PLW0603
    _restart_requested = True
    if _shutdown_callback is not None:
        await _shutdown_callback()


def should_restart() -> bool:
    return _restart_requested


def reset_restart() -> None:
    global _restart_requested  # noqa: PLW0603
    _restart_requested = False
