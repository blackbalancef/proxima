from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from proxima.claude.session_watchdog import SessionWatchdog


def _make_session(session_id: int = 1) -> MagicMock:
    s = MagicMock()
    s.id = session_id
    s.status = "active"
    s.last_activity = datetime.now(UTC) - timedelta(hours=1)
    return s


@pytest.fixture
def watchdog() -> tuple[SessionWatchdog, AsyncMock, AsyncMock]:
    sessions = AsyncMock()
    bot = AsyncMock()
    wd = SessionWatchdog(sessions=sessions, bot=bot, timeout_minutes=30)
    return wd, sessions, bot


async def test_check_stale_marks_idle_and_notifies(
    watchdog: tuple[SessionWatchdog, AsyncMock, AsyncMock],
) -> None:
    wd, sessions, bot = watchdog
    session = _make_session()
    chat_id = 12345
    sessions.find_stale_sessions_with_chat.return_value = [(session, chat_id, None)]
    sessions.mark_idle.return_value = None
    bot.send_message.return_value = None

    await wd._check_stale()

    sessions.find_stale_sessions_with_chat.assert_awaited_once_with(30)
    sessions.mark_idle.assert_awaited_once_with(session.id)
    bot.send_message.assert_awaited_once()
    call_args = bot.send_message.call_args
    assert call_args[0][0] == chat_id


async def test_check_stale_no_stale_sessions(
    watchdog: tuple[SessionWatchdog, AsyncMock, AsyncMock],
) -> None:
    wd, sessions, bot = watchdog
    sessions.find_stale_sessions_with_chat.return_value = []

    await wd._check_stale()

    sessions.mark_idle.assert_not_awaited()
    bot.send_message.assert_not_awaited()


async def test_timeout_property(
    watchdog: tuple[SessionWatchdog, AsyncMock, AsyncMock],
) -> None:
    wd, _, _ = watchdog
    assert wd.timeout_minutes == 30
    wd.timeout_minutes = 60
    assert wd.timeout_minutes == 60
    wd.timeout_minutes = 0  # should clamp to 1
    assert wd.timeout_minutes == 1


async def test_start_stop(
    watchdog: tuple[SessionWatchdog, AsyncMock, AsyncMock],
) -> None:
    wd, sessions, _ = watchdog
    sessions.find_stale_sessions_with_chat.return_value = []

    await wd.start()
    assert wd._task is not None
    await wd.stop()
    assert wd._task is None
