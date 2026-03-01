from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram import Bot

from proxima.logging import get_logger
from proxima.telegram.keyboards import build_permission_keyboard

logger = get_logger(__name__)


@dataclass
class PendingPermission:
    future: asyncio.Future[bool]
    tool_name: str
    telegram_message_id: int | None = None


class PermissionHandler:
    def __init__(self, bot: Bot, chat_id: int, message_thread_id: int | None = None) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self._pending: dict[str, PendingPermission] = {}
        self._counter = 0
        self._allow_all_session = False

    def _next_id(self) -> str:
        self._counter += 1
        return f"{self.chat_id}:{self._counter}"

    async def request_permission(self, tool_name: str, tool_input: dict[str, object]) -> bool:
        if self._allow_all_session:
            logger.debug("permission_auto_allow", tool=tool_name)
            return True

        logger.info("permission_requested", tool=tool_name, chat_id=self.chat_id)
        request_id = self._next_id()
        detail = ""
        if "command" in tool_input:
            detail = f"\nCommand: {str(tool_input['command'])[:200]}"
        elif "file_path" in tool_input:
            detail = f"\nFile: {tool_input['file_path']}"
        elif "pattern" in tool_input:
            detail = f"\nPattern: {tool_input['pattern']}"

        text = f"Permission request\n\nTool: {tool_name}{detail}"
        keyboard = build_permission_keyboard(request_id)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending[request_id] = PendingPermission(future=future, tool_name=tool_name)

        try:
            message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=keyboard,
                message_thread_id=self.message_thread_id,
            )
            self._pending[request_id].telegram_message_id = message.message_id
        except Exception as exc:  # noqa: BLE001
            logger.exception("permission_message_send_failed", error=str(exc))
            self._pending.pop(request_id, None)
            return False

        async def timeout() -> None:
            await asyncio.sleep(5 * 60)
            pending = self._pending.pop(request_id, None)
            if pending and not pending.future.done():
                pending.future.set_result(False)
                logger.warning("permission_request_timeout", request_id=request_id)

        asyncio.create_task(timeout())
        return await future

    async def handle_callback(
        self,
        data: str,
        answer_callback: Callable[[], Awaitable[None]],
    ) -> bool:
        parts = data.split(":")
        if not parts or parts[0] != "perm":
            return False

        if len(parts) < 4:
            return False

        action = parts[1]
        request_id = ":".join(parts[2:])
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return False

        allowed = False
        status_text = "Denied"

        if action == "allow":
            allowed = True
            status_text = f"Allowed: {pending.tool_name}"
        elif action == "deny":
            allowed = False
            status_text = f"Denied: {pending.tool_name}"
        elif action == "allow_all":
            allowed = True
            self._allow_all_session = True
            status_text = f"Allowed all for session: {pending.tool_name}"
        else:
            return False

        logger.info(
            "permission_callback",
            action=action,
            tool=pending.tool_name,
            chat_id=self.chat_id,
        )

        if pending.telegram_message_id:
            try:
                await self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=pending.telegram_message_id,
                    text=status_text,
                )
            except Exception:
                pass

        await answer_callback()
        if not pending.future.done():
            pending.future.set_result(allowed)
        return True

    def reset_allow_all(self) -> None:
        self._allow_all_session = False

    def cleanup(self) -> None:
        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.set_result(False)
        self._pending.clear()


_handlers: dict[tuple[int, int | None], PermissionHandler] = {}


def get_permission_handler(
    bot: Bot, chat_id: int, thread_id: int | None = None
) -> PermissionHandler:
    key = (chat_id, thread_id)
    handler = _handlers.get(key)
    if not handler:
        handler = PermissionHandler(bot, chat_id, message_thread_id=thread_id)
        _handlers[key] = handler
    return handler


def find_permission_handler(
    chat_id: int, thread_id: int | None = None
) -> PermissionHandler | None:
    return _handlers.get((chat_id, thread_id))
