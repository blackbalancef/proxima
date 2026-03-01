from __future__ import annotations

import asyncio
import os
import sys

from aiogram import Bot
from aiogram.types import BotCommand

from proxima.bot.factory import create_dispatcher
from proxima.db.migrate import run_migrations
from proxima.lifecycle import reset_restart, setup_signal_handlers, should_restart
from proxima.logging import configure_logging, get_logger
from proxima.services import Services, build_services
from proxima.settings import get_settings

logger = get_logger(__name__)


class App:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.bot = Bot(token=services.settings.telegram_bot_token)
        self.dispatcher = create_dispatcher(services)
        self._shutdown_requested = asyncio.Event()

    async def run(self) -> None:
        setup_signal_handlers(self.shutdown)
        await run_migrations(self.services.db.engine)

        await _set_bot_commands(self.bot)

        logger.info("starting_bot")
        polling = asyncio.create_task(
            self.dispatcher.start_polling(
                self.bot,
                allowed_updates=self.dispatcher.resolve_used_update_types(),
            )
        )

        await self._shutdown_requested.wait()
        await self.dispatcher.stop_polling()
        await polling

    async def shutdown(self) -> None:
        if self._shutdown_requested.is_set():
            return
        self._shutdown_requested.set()
        logger.info("shutting_down")

    async def close(self) -> None:
        await self.bot.session.close()
        await self.services.db.close()


_BOT_COMMANDS = [
    BotCommand(command="start", description="Welcome & project list"),
    BotCommand(command="help_prox", description="Show all commands"),
    BotCommand(command="new_prox", description="Create project"),
    BotCommand(command="clone_prox", description="Clone git repo as project"),
    BotCommand(command="projects_prox", description="List projects"),
    BotCommand(command="delete_prox", description="Delete project"),
    BotCommand(command="rename_prox", description="Rename project"),
    BotCommand(command="thread_prox", description="New thread session"),
    BotCommand(command="reset_prox", description="Reset session"),
    BotCommand(command="cancel_prox", description="Cancel running query"),
    BotCommand(command="info_prox", description="Project & session info"),
    BotCommand(command="model_prox", description="Select Claude model"),
    BotCommand(command="mode_prox", description="Plan / Execute mode"),
    BotCommand(command="permissions_prox", description="Permission presets"),
    BotCommand(command="mcp_prox", description="MCP server config"),
    BotCommand(command="memory_prox", description="CLAUDE.md management"),
    BotCommand(command="cmd_prox", description="Custom slash commands"),
    BotCommand(command="config_prox", description="Bot configuration"),
    BotCommand(command="server_prox", description="Host info"),
    BotCommand(command="users_prox", description="Allowed users"),
    BotCommand(command="update_prox", description="Update & restart bot"),
]


async def _set_bot_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands(_BOT_COMMANDS)
        logger.info("bot_commands_set", count=len(_BOT_COMMANDS))
    except Exception:
        logger.exception("bot_commands_set_failed")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    services = build_services(settings)
    app = App(services)

    try:
        await app.run()
    finally:
        await app.close()


def main_cli() -> None:
    asyncio.run(main())

    if should_restart():
        reset_restart()
        os.execv(sys.executable, [sys.executable, "-m", "proxima.main"])


if __name__ == "__main__":
    main_cli()
