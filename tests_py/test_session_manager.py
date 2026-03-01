from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from proxima.claude.session_manager import SessionManager


def _make_session(
    session_id: int = 1,
    project_id: int = 10,
    claude_session_id: str | None = "cs-123",
    status: str = "active",
) -> MagicMock:
    s = MagicMock()
    s.id = session_id
    s.project_id = project_id
    s.claude_session_id = claude_session_id
    s.status = status
    return s


@pytest.fixture
def manager() -> tuple[SessionManager, AsyncMock]:
    repo = AsyncMock()
    return SessionManager(repo), repo


async def test_get_or_create_returns_existing_active(
    manager: tuple[SessionManager, AsyncMock],
) -> None:
    mgr, repo = manager
    existing = _make_session()
    repo.find_active_by_project.return_value = existing

    result = await mgr.get_or_create(10)

    assert result.db_id == existing.id
    assert result.resumed is False
    repo.find_idle_by_project.assert_not_awaited()


async def test_get_or_create_resumes_idle_session(
    manager: tuple[SessionManager, AsyncMock],
) -> None:
    mgr, repo = manager
    repo.find_active_by_project.return_value = None
    idle = _make_session(status="idle")
    repo.find_idle_by_project.return_value = idle

    result = await mgr.get_or_create(10)

    assert result.db_id == idle.id
    assert result.resumed is True
    repo.update.assert_awaited_once_with(idle.id, {"status": "active"})


async def test_get_or_create_creates_new(
    manager: tuple[SessionManager, AsyncMock],
) -> None:
    mgr, repo = manager
    repo.find_active_by_project.return_value = None
    repo.find_idle_by_project.return_value = None
    new_session = _make_session(claude_session_id=None)
    repo.create.return_value = new_session

    result = await mgr.get_or_create(10)

    assert result.db_id == new_session.id
    assert result.resumed is False
    assert result.claude_session_id is None
    repo.create.assert_awaited_once()


async def test_reset_session(
    manager: tuple[SessionManager, AsyncMock],
) -> None:
    mgr, repo = manager
    await mgr.reset_session(10)
    repo.close_by_project.assert_awaited_once_with(10)
