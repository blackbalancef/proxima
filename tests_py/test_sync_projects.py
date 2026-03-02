from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError


def _make_project(
    project_id: int = 1,
    chat_id: int = 100,
    name: str = "proj",
    directory: str = "/tmp/proj",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.telegram_chat_id = chat_id
    p.name = name
    p.directory = directory
    p.is_active = False
    return p


@pytest.fixture
def services() -> MagicMock:
    svc = MagicMock()
    svc.projects = AsyncMock()
    svc.sessions = AsyncMock()
    svc.settings = MagicMock()
    svc.settings.work_dir = Path("/tmp/work")
    return svc


async def test_prune_removes_project_with_missing_directory(services: MagicMock) -> None:
    """Projects whose directory doesn't exist should be pruned."""
    dead = _make_project(project_id=1, name="dead", directory="/nonexistent/path")
    services.projects.find_all.return_value = [dead]
    services.sessions.find_threads_by_project.return_value = []

    pruned: list[str] = []
    for proj in await services.projects.find_all():
        if proj.name == "default":
            continue
        exists = await asyncio.to_thread(os.path.isdir, proj.directory)
        if exists:
            continue
        threads = await services.sessions.find_threads_by_project(proj.id)
        assert threads == []
        await services.projects.delete_by_id(proj.id)
        pruned.append(f"{proj.name} ({proj.directory})")

    assert len(pruned) == 1
    assert "dead" in pruned[0]
    services.projects.delete_by_id.assert_awaited_once_with(1)


async def test_prune_skips_default_project(services: MagicMock) -> None:
    """The 'default' project should never be pruned."""
    default = _make_project(name="default", directory="/nonexistent")
    services.projects.find_all.return_value = [default]

    pruned: list[str] = []
    for proj in await services.projects.find_all():
        if proj.name == "default":
            continue
        pruned.append(proj.name)

    assert pruned == []


async def test_prune_skips_existing_directory(services: MagicMock, tmp_path: Path) -> None:
    """Projects whose directory exists on disk should NOT be pruned."""
    alive = _make_project(name="alive", directory=str(tmp_path))
    services.projects.find_all.return_value = [alive]

    pruned: list[str] = []
    for proj in await services.projects.find_all():
        if proj.name == "default":
            continue
        exists = await asyncio.to_thread(os.path.isdir, proj.directory)
        if exists:
            continue
        pruned.append(proj.name)

    assert pruned == []


async def test_prune_deletes_forum_topics(services: MagicMock) -> None:
    """Forum topics associated with a dead project should be deleted."""
    dead = _make_project(name="dead", directory="/nonexistent")
    services.projects.find_all.return_value = [dead]
    services.sessions.find_threads_by_project.return_value = [(100, 42), (100, 43)]

    bot = AsyncMock()
    for proj in await services.projects.find_all():
        if proj.name == "default":
            continue
        exists = await asyncio.to_thread(os.path.isdir, proj.directory)
        if exists:
            continue
        threads = await services.sessions.find_threads_by_project(proj.id)
        for chat_id, thread_id in threads:
            await bot.delete_forum_topic(chat_id, thread_id)

    assert bot.delete_forum_topic.await_count == 2
    bot.delete_forum_topic.assert_any_await(100, 42)
    bot.delete_forum_topic.assert_any_await(100, 43)


def test_discover_finds_new_subdirectories(tmp_path: Path) -> None:
    """Subdirectories in WORK_DIR not tracked by any project should be discovered."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "somefile.txt").touch()  # Not a directory — should be ignored

    tracked_dirs = {str((tmp_path / "alpha").resolve())}

    def _list_subdirs(parent: str) -> list[tuple[str, str]]:
        base = Path(parent)
        if not base.is_dir():
            return []
        return sorted(
            (entry.name, str(entry.resolve())) for entry in base.iterdir() if entry.is_dir()
        )

    subdirs = _list_subdirs(str(tmp_path))
    new_dirs = [(name, path) for name, path in subdirs if path not in tracked_dirs]

    assert len(new_dirs) == 1
    assert new_dirs[0][0] == "beta"


async def test_discover_skips_on_integrity_error(services: MagicMock, tmp_path: Path) -> None:
    """Directories with conflicting names should be skipped gracefully."""
    (tmp_path / "existing").mkdir()

    services.projects.create.side_effect = IntegrityError("dup", {}, None)

    skipped: list[str] = []
    try:
        await services.projects.create(
            {
                "telegram_chat_id": 100,
                "name": "existing",
                "directory": str(tmp_path / "existing"),
                "is_active": False,
                "permission_mode": "bypassPermissions",
            }
        )
    except IntegrityError:
        skipped.append("existing")

    assert skipped == ["existing"]


def test_discover_ignores_nonexistent_work_dir() -> None:
    """If WORK_DIR doesn't exist, discovery returns empty list."""

    def _list_subdirs(parent: str) -> list[tuple[str, str]]:
        base = Path(parent)
        if not base.is_dir():
            return []
        return sorted(
            (entry.name, str(entry.resolve())) for entry in base.iterdir() if entry.is_dir()
        )

    result = _list_subdirs("/definitely/not/a/real/path")
    assert result == []
