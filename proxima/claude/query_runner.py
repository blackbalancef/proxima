from __future__ import annotations

import asyncio
from typing import Any

from proxima.logging import get_logger

logger = get_logger(__name__)

type _Key = tuple[int, int | None]

_active_tasks: dict[_Key, asyncio.Task[Any]] = {}


def set_active_task(key: _Key, task: asyncio.Task[Any]) -> None:
    existing = _active_tasks.get(key)
    if existing and not existing.done():
        logger.warning("replacing_active_task", key=key)
        existing.cancel()
    _active_tasks[key] = task
    logger.debug("task_registered", key=key)


def cancel_query(key: _Key) -> bool:
    task = _active_tasks.get(key)
    if task and not task.done():
        task.cancel()
        _active_tasks.pop(key, None)
        logger.info("query_cancelled", key=key)
        return True
    logger.debug("cancel_no_active_task", key=key)
    return False


def clear_task(key: _Key) -> None:
    _active_tasks.pop(key, None)
    logger.debug("task_cleared", key=key)
