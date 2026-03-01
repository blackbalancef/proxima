from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable, Coroutine
from typing import Any

ShutdownCallback = Callable[[], Coroutine[Any, Any, None]]


def setup_signal_handlers(shutdown_cb: ShutdownCallback) -> None:
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown_cb()))
