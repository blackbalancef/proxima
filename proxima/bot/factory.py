from __future__ import annotations

from aiogram import Dispatcher

from proxima.bot.middlewares import AuthMiddleware, ProjectResolverMiddleware
from proxima.bot.router import build_router
from proxima.logging import get_logger
from proxima.services import Services

logger = get_logger(__name__)


def create_dispatcher(services: Services) -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(AuthMiddleware(services.settings.allowed_user_ids))
    dp.update.middleware(ProjectResolverMiddleware(services))
    dp.include_router(build_router(services))

    @dp.errors()
    async def on_error(event) -> bool:  # type: ignore[no-untyped-def]
        logger.exception("bot_error", error=str(event.exception), update=event.update)
        return True

    return dp
