from __future__ import annotations

from dataclasses import dataclass, field

from proxima.db.repositories.session import SessionRepository
from proxima.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ActiveSession:
    db_id: int
    project_id: int
    claude_session_id: str | None
    thread_id: int | None = None
    resumed: bool = field(default=False)
    model: str | None = field(default=None)


class SessionManager:
    def __init__(self, session_repo: SessionRepository) -> None:
        self.session_repo = session_repo

    async def get_or_create(
        self, project_id: int, *, thread_id: int | None = None, chat_id: int | None = None
    ) -> ActiveSession:
        if thread_id is not None and chat_id is not None:
            return await self._get_or_create_thread(project_id, chat_id, thread_id)
        return await self._get_or_create_project(project_id)

    async def _get_or_create_project(self, project_id: int) -> ActiveSession:
        existing = await self.session_repo.find_active_by_project(project_id)
        if existing:
            logger.debug(
                "session_found",
                db_id=existing.id,
                project_id=project_id,
                has_claude_session=existing.claude_session_id is not None,
            )
            return ActiveSession(
                db_id=existing.id,
                project_id=existing.project_id,
                claude_session_id=existing.claude_session_id,
                model=existing.model,
            )

        idle = await self.session_repo.find_idle_by_project(project_id)
        if idle:
            await self.session_repo.update(idle.id, {"status": "active"})
            logger.info("session_resumed_from_idle", db_id=idle.id, project_id=project_id)
            return ActiveSession(
                db_id=idle.id,
                project_id=idle.project_id,
                claude_session_id=idle.claude_session_id,
                resumed=True,
                model=idle.model,
            )

        session = await self.session_repo.create({"project_id": project_id, "status": "active"})
        logger.info("session_created", db_id=session.id, project_id=project_id)
        return ActiveSession(
            db_id=session.id, project_id=session.project_id, claude_session_id=None
        )

    async def _get_or_create_thread(
        self, project_id: int, chat_id: int, thread_id: int
    ) -> ActiveSession:
        existing = await self.session_repo.find_active_by_thread(chat_id, thread_id)
        if existing:
            logger.debug(
                "thread_session_found",
                db_id=existing.id,
                thread_id=thread_id,
                has_claude_session=existing.claude_session_id is not None,
            )
            return ActiveSession(
                db_id=existing.id,
                project_id=existing.project_id,
                claude_session_id=existing.claude_session_id,
                thread_id=thread_id,
                model=existing.model,
            )

        idle = await self.session_repo.find_idle_by_thread(chat_id, thread_id)
        if idle:
            await self.session_repo.update(idle.id, {"status": "active"})
            logger.info(
                "thread_session_resumed_from_idle",
                db_id=idle.id,
                thread_id=thread_id,
            )
            return ActiveSession(
                db_id=idle.id,
                project_id=idle.project_id,
                claude_session_id=idle.claude_session_id,
                thread_id=thread_id,
                resumed=True,
                model=idle.model,
            )

        session = await self.session_repo.create(
            {"project_id": project_id, "status": "active", "message_thread_id": thread_id}
        )
        logger.info("thread_session_created", db_id=session.id, thread_id=thread_id)
        return ActiveSession(
            db_id=session.id, project_id=session.project_id, claude_session_id=None,
            thread_id=thread_id,
        )

    async def update_model(self, db_id: int, model: str | None) -> None:
        await self.session_repo.update(db_id, {"model": model})
        logger.debug("session_model_updated", db_id=db_id, model=model)

    async def update_claude_session_id(self, db_id: int, claude_session_id: str) -> None:
        await self.session_repo.update(db_id, {"claude_session_id": claude_session_id})
        logger.debug("claude_session_id_updated", db_id=db_id, claude_session_id=claude_session_id)

    async def touch_activity(self, db_id: int) -> None:
        await self.session_repo.touch_activity(db_id)

    async def reset_session(self, project_id: int) -> None:
        await self.session_repo.close_by_project(project_id)
        logger.info("session_reset", project_id=project_id)

    async def reset_thread_session(self, chat_id: int, thread_id: int) -> None:
        await self.session_repo.close_by_thread(chat_id, thread_id)
        logger.info("thread_session_reset", chat_id=chat_id, thread_id=thread_id)
