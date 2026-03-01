from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy.exc import IntegrityError

from proxima.logging import get_logger
from proxima.services import Services

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, allowed_user_ids: list[int]) -> None:
        self.allowed_user_ids = set(allowed_user_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user or user.id not in self.allowed_user_ids:
            user_id = user.id if user else None
            logger.warning("auth_rejected", user_id=user_id)
            return None
        return await handler(event, data)


class ProjectResolverMiddleware(BaseMiddleware):
    def __init__(self, services: Services) -> None:
        self.services = services

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = data.get("event_chat")
        if not chat:
            return await handler(event, data)

        thread_id = self._extract_thread_id(event)
        data["thread_id"] = thread_id

        project = None
        if thread_id is not None:
            latest = await self.services.sessions.find_latest_by_thread(chat.id, thread_id)
            if latest:
                project = await self.services.projects.find_by_id(latest.project_id)

        if project is None:
            project = await self.services.projects.find_active_by_chat(chat.id)

        if project is None:
            all_projects = await self.services.projects.find_all_by_chat(chat.id)
            if all_projects:
                project = all_projects[0]
                await self.services.projects.set_active(chat.id, project.id)
            else:
                try:
                    project = await self.services.projects.create(
                        {
                            "telegram_chat_id": chat.id,
                            "name": "default",
                            "directory": str(self.services.settings.work_dir),
                            "is_active": True,
                            "permission_mode": "bypassPermissions",
                        }
                    )
                    logger.info("default_project_created", chat_id=chat.id)
                except IntegrityError:
                    project = await self.services.projects.find_active_by_chat(chat.id)

        data["project"] = project
        return await handler(event, data)

    @staticmethod
    def _extract_thread_id(event: TelegramObject) -> int | None:
        if isinstance(event, Update):
            if event.message:
                return event.message.message_thread_id
            if event.callback_query and event.callback_query.message:
                return event.callback_query.message.message_thread_id  # type: ignore[union-attr]
            return None
        if isinstance(event, Message):
            return event.message_thread_id
        if isinstance(event, CallbackQuery) and event.message:
            return event.message.message_thread_id  # type: ignore[union-attr]
        return None
