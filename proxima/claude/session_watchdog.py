from __future__ import annotations

import asyncio

from aiogram import Bot

from proxima.db.repositories.session import SessionRepository
from proxima.logging import get_logger

logger = get_logger(__name__)

CHECK_INTERVAL = 60  # seconds


class SessionWatchdog:
    def __init__(
        self,
        sessions: SessionRepository,
        bot: Bot,
        timeout_minutes: int,
    ) -> None:
        self._sessions = sessions
        self._bot = bot
        self._timeout = timeout_minutes
        self._task: asyncio.Task[None] | None = None

    @property
    def timeout_minutes(self) -> int:
        return self._timeout

    @timeout_minutes.setter
    def timeout_minutes(self, value: int) -> None:
        self._timeout = max(1, value)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("session_watchdog_started", timeout_minutes=self._timeout)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("session_watchdog_stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL)
                await self._check_stale()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("session_watchdog_error")

    async def _check_stale(self) -> None:
        stale = await self._sessions.find_stale_sessions_with_chat(self._timeout)
        for session, chat_id, thread_id in stale:
            await self._sessions.mark_idle(session.id)
            logger.info(
                "session_marked_idle",
                session_id=session.id,
                chat_id=chat_id,
                thread_id=thread_id,
            )
            try:
                await self._bot.send_message(
                    chat_id,
                    f"Session idle (no activity for {self._timeout} min). "
                    "Next message will resume automatically.",
                    message_thread_id=thread_id,
                )
            except Exception:
                logger.exception("session_idle_notify_failed", chat_id=chat_id)
