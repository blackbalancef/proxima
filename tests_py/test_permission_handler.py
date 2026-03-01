import asyncio

import pytest

from proxima.claude.permission_handler import PermissionHandler


class FakeMessage:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class FakeBot:
    def __init__(self) -> None:
        self.sent = 0
        self.edited: list[str] = []

    async def send_message(  # type: ignore[no-untyped-def]
        self, chat_id: int, text: str, reply_markup=None, message_thread_id=None
    ):
        self.sent += 1
        return FakeMessage(self.sent)

    async def edit_message_text(self, chat_id: int, message_id: int, text: str):  # type: ignore[no-untyped-def]
        self.edited.append(text)
        return True


@pytest.mark.asyncio
async def test_permission_allow_flow() -> None:
    bot = FakeBot()
    handler = PermissionHandler(bot, 1)  # type: ignore[arg-type]

    task = asyncio.create_task(handler.request_permission("Bash", {"command": "ls"}))
    await asyncio.sleep(0.01)

    handled = await handler.handle_callback("perm:allow:1:1", lambda: asyncio.sleep(0))
    assert handled is True
    assert await task is True


@pytest.mark.asyncio
async def test_permission_allow_all_auto_approves_next() -> None:
    bot = FakeBot()
    handler = PermissionHandler(bot, 1)  # type: ignore[arg-type]

    first = asyncio.create_task(handler.request_permission("Read", {}))
    await asyncio.sleep(0.01)
    await handler.handle_callback("perm:allow_all:1:1", lambda: asyncio.sleep(0))
    assert await first is True

    second = await handler.request_permission("Write", {})
    assert second is True
    assert bot.sent == 1
