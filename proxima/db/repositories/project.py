from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import desc, select, update

from proxima.db.engine import Database
from proxima.db.models import Project


class ProjectRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def find_active_by_chat(self, chat_id: int) -> Project | None:
        async with self.db.session() as session:
            result = await session.execute(
                select(Project)
                .where(Project.telegram_chat_id == chat_id)
                .where(Project.is_active.is_(True))
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def find_all(self) -> list[Project]:
        async with self.db.session() as session:
            result = await session.execute(select(Project))
            return list(result.scalars().all())

    async def find_all_by_chat(self, chat_id: int) -> list[Project]:
        async with self.db.session() as session:
            result = await session.execute(
                select(Project)
                .where(Project.telegram_chat_id == chat_id)
                .order_by(desc(Project.created_at))
            )
            return list(result.scalars().all())

    async def find_by_id(self, project_id: int) -> Project | None:
        async with self.db.session() as session:
            result = await session.execute(select(Project).where(Project.id == project_id).limit(1))
            return result.scalar_one_or_none()

    async def create(self, values: Mapping[str, Any]) -> Project:
        project = Project(**dict(values))
        async with self.db.session() as session:
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return project

    async def update(self, project_id: int, values: Mapping[str, Any]) -> Project | None:
        async with self.db.session() as session:
            result = await session.execute(select(Project).where(Project.id == project_id).limit(1))
            project = result.scalar_one_or_none()
            if not project:
                return None
            for key, value in values.items():
                setattr(project, key, value)
            await session.commit()
            await session.refresh(project)
            return project

    async def set_active(self, chat_id: int, project_id: int) -> None:
        async with self.db.session() as session:
            await session.execute(
                update(Project).where(Project.telegram_chat_id == chat_id).values(is_active=False)
            )
            await session.execute(
                update(Project).where(Project.id == project_id).values(is_active=True)
            )
            await session.commit()

    async def delete_by_id(self, project_id: int) -> None:
        async with self.db.session() as session:
            project = await session.get(Project, project_id)
            if project is None:
                return
            await session.delete(project)
            await session.commit()
