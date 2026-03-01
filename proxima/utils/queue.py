from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Hashable

from proxima.logging import get_logger

logger = get_logger(__name__)

type QueueTask = Callable[[], Awaitable[None]]


class SequentialQueue:
    """Per-key sequential queue with cross-key concurrency."""

    def __init__(self) -> None:
        self._queues: dict[Hashable, deque[QueueTask]] = defaultdict(deque)
        self._running: set[Hashable] = set()

    def enqueue(self, key: Hashable, task: QueueTask) -> None:
        self._queues[key].append(task)
        queue_size = len(self._queues[key])
        logger.debug("task_enqueued", key=key, queue_size=queue_size)
        asyncio.create_task(self._process(key))

    async def _process(self, key: Hashable) -> None:
        if key in self._running:
            return

        self._running.add(key)
        try:
            while self._queues[key]:
                current = self._queues[key].popleft()
                try:
                    await current()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("queue_task_failed", key=key, error=str(exc))
        finally:
            self._running.discard(key)
            if not self._queues[key]:
                del self._queues[key]


message_queue = SequentialQueue()
