from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, desc, func, select, update

from proxima.db.engine import Database
from proxima.db.models import Project, Session


class SessionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def find_active_by_project(self, project_id: int) -> Session | None:
        async with self.db.session() as session:
            result = await session.execute(
                select(Session)
                .where(Session.project_id == project_id)
                .where(Session.status == "active")
                .order_by(desc(Session.last_activity))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def find_active_by_thread(self, chat_id: int, thread_id: int) -> Session | None:
        async with self.db.session() as session:
            result = await session.execute(
                select(Session)
                .join(Project, Session.project_id == Project.id)
                .where(Project.telegram_chat_id == chat_id)
                .where(Session.message_thread_id == thread_id)
                .where(Session.status == "active")
                .order_by(desc(Session.last_activity))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def find_latest_by_thread(self, chat_id: int, thread_id: int) -> Session | None:
        async with self.db.session() as session:
            result = await session.execute(
                select(Session)
                .join(Project, Session.project_id == Project.id)
                .where(Project.telegram_chat_id == chat_id)
                .where(Session.message_thread_id == thread_id)
                .order_by(desc(Session.last_activity))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def close_by_thread(self, chat_id: int, thread_id: int) -> None:
        async with self.db.session() as session:
            subq = (
                select(Session.id)
                .join(Project, Session.project_id == Project.id)
                .where(Project.telegram_chat_id == chat_id)
                .where(Session.message_thread_id == thread_id)
                .where(Session.status == "active")
            )
            await session.execute(
                update(Session).where(Session.id.in_(subq)).values(status="closed")
            )
            await session.commit()

    async def create(self, values: Mapping[str, Any]) -> Session:
        db_session = Session(**dict(values))
        async with self.db.session() as session:
            session.add(db_session)
            await session.commit()
            await session.refresh(db_session)
            return db_session

    async def update(self, session_id: int, values: Mapping[str, Any]) -> Session | None:
        async with self.db.session() as session:
            result = await session.execute(select(Session).where(Session.id == session_id).limit(1))
            db_session = result.scalar_one_or_none()
            if not db_session:
                return None
            for key, value in values.items():
                setattr(db_session, key, value)
            await session.commit()
            await session.refresh(db_session)
            return db_session

    async def close_by_project(self, project_id: int) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(Session)
                .where(Session.project_id == project_id)
                .where(Session.status == "active")
                .values(status="closed")
            )
            await session.commit()

    async def delete_by_thread(self, chat_id: int, thread_id: int) -> None:
        async with self.db.session() as session:
            subq = (
                select(Session.id)
                .join(Project, Session.project_id == Project.id)
                .where(Project.telegram_chat_id == chat_id)
                .where(Session.message_thread_id == thread_id)
            )
            await session.execute(delete(Session).where(Session.id.in_(subq)))
            await session.commit()

    async def delete_by_id(self, session_id: int) -> None:
        async with self.db.session() as session:
            await session.execute(delete(Session).where(Session.id == session_id))
            await session.commit()

    async def find_threads_by_project(self, project_id: int) -> list[tuple[int, int]]:
        """Return (chat_id, thread_id) pairs for all thread sessions of a project."""
        async with self.db.session() as session:
            result = await session.execute(
                select(Project.telegram_chat_id, Session.message_thread_id)
                .join(Project, Session.project_id == Project.id)
                .where(Session.project_id == project_id)
                .where(Session.message_thread_id.is_not(None))
                .distinct()
            )
            return [(row[0], row[1]) for row in result.all()]

    async def count_threads_by_project(self, project_id: int) -> int:
        async with self.db.session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(Session)
                .where(Session.project_id == project_id)
                .where(Session.message_thread_id.is_not(None))
            )
            return result.scalar_one()
